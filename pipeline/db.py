"""
SQLite schema and status-tracking logic for the vulnerability tracker.

Design notes (the "why" behind the schema, worth remembering for
interview storytelling):

- A finding's identity is (nvt_oid, host, port) - NOT task_name. The same
  vulnerable service found by both an authenticated and unauthenticated
  scan of the same host is one tracked row, not two. task_name just
  reflects whichever scan most recently touched that row.

- Status is only ever set to 'Remediated' or reopened to 'Open' by this
  script's own logic, based on presence/absence in the newest scan of a
  given host. 'In Progress' is a manual status you set yourself (e.g. via
  a small update script or directly in the DB) to mean "I'm working this" -
  the ingestion logic never overwrites it.

- ingested_reports exists purely so re-running main.py against a report
  you've already processed is a safe no-op rather than double-counting.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Iterable, List

from .parser import Finding

SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nvt_oid TEXT NOT NULL,
    host TEXT NOT NULL,
    port TEXT NOT NULL,
    name TEXT NOT NULL,
    severity REAL NOT NULL,
    qod REAL NOT NULL DEFAULT 0,
    threat TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'Open',
    task_name TEXT,
    report_id TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(nvt_oid, host, port)
);

CREATE TABLE IF NOT EXISTS ingested_reports (
    report_id TEXT PRIMARY KEY,
    task_name TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    # Opens (or creates, if it doesn't exist yet) the SQLite file, then makes
    # sure all three tables above exist before handing back the connection.
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def already_ingested(conn: sqlite3.Connection, report_id: str) -> bool:
    # True if we already have a row for this report_id, meaning we've
    # processed it before and should skip it this run.
    row = conn.execute(
        "SELECT 1 FROM ingested_reports WHERE report_id = ?", (report_id,)
    ).fetchone()
    return row is not None


def mark_ingested(conn: sqlite3.Connection, report_id: str, task_name: str):
    # Records that this report has now been processed, so a future run
    # (or a rerun of this one) won't ingest it a second time.
    conn.execute(
        "INSERT OR REPLACE INTO ingested_reports (report_id, task_name, ingested_at) "
        "VALUES (?, ?, ?)",
        (report_id, task_name, datetime.now(timezone.utc).isoformat()),
    )

def get_last_run(conn: sqlite3.Connection) -> str | None:
    """Returns the ISO8601 timestamp of the last successful pipeline run,
    or None if this is the first run ever."""
    row = conn.execute(
        "SELECT value FROM pipeline_state WHERE key = 'last_run'"
    ).fetchone()
    return row[0] if row else None


def set_last_run(conn: sqlite3.Connection, timestamp: str):
    """Records the current run's start time, so the NEXT run can ask
    gvmd for only reports created after this point."""
    conn.execute(
        "INSERT OR REPLACE INTO pipeline_state (key, value) VALUES ('last_run', ?)",
        (timestamp,),
    )


def upsert_findings(conn: sqlite3.Connection, findings: Iterable[Finding]):
    """Insert new findings as 'Open', or update existing ones' last_seen /
    report info. If a finding was 'Remediated' and shows up again, it's
    reopened - a scanner seeing it again means it's back, regardless of
    what we thought before."""
    now = datetime.now(timezone.utc).isoformat()

    for f in findings:
        # Step 1: check if we already have a row for this exact
        # vulnerability + host + port combo.
        existing = conn.execute(
            "SELECT id, status FROM findings WHERE nvt_oid = ? AND host = ? AND port = ?",
            (f.nvt_oid, f.host, f.port),
        ).fetchone()

        if existing is None:
            # Step 2a: never seen before - insert it as a brand-new Open finding.
            conn.execute(
                """INSERT INTO findings
                    (nvt_oid, host, port, name, severity, qod, threat, description,
                    status, task_name, report_id, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?)""",
                (f.nvt_oid, f.host, f.port, f.name, f.severity, f.qod, f.threat, f.description, f.task_name, f.report_id, now, now),
)
        else:
            # Step 2b: already tracked - update it, and if it had been marked
            # Remediated, flip it back to Open since the scanner just found it
            # again. Any other status (Open, In Progress) is left alone.
            finding_id, status = existing
            new_status = "Open" if status == "Remediated" else status
            conn.execute(
                """UPDATE findings
                   SET last_seen = ?, task_name = ?, report_id = ?,
                       severity = ?, qod = ?, threat = ?, status = ?
                   WHERE id = ?""",
                (now, f.task_name, f.report_id, f.severity, f.qod, f.threat,
                 new_status, finding_id),
            )

def get_findings(conn: sqlite3.Connection, task_name: str | None = None,
                  sort_by: str = "severity") -> list:
    "Whitelist the sort column to avoid SQL injection, then return all findings optionally filtered by task_name."
    sort_column = {"severity": "severity", "qod": "qod"}.get(sort_by, "severity")

    query = "SELECT name, host, port, severity, qod, threat, status, task_name FROM findings"
    params: tuple = ()
    if task_name:
        query += " WHERE task_name = ?"
        params = (task_name,)
    query += f" ORDER BY {sort_column} DESC"

    return conn.execute(query, params).fetchall()

def close_out_missing_findings(conn: sqlite3.Connection, host: str,
                                 seen_nvt_oids_ports: set):
    """For a host that was just rescanned, mark anything not 'In Progress'
    and not present in seen_nvt_oids_ports (a set of (nvt_oid, port) tuples)
    as Remediated. Only call this for hosts that were actually covered by
    the report you just ingested - see hosts_in_report() in parser.py."""
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: get every finding for this host that isn't already Remediated.
    rows = conn.execute(
        "SELECT id, nvt_oid, port, status FROM findings WHERE host = ? AND status != 'Remediated'",
        (host,),
    ).fetchall()

    for finding_id, nvt_oid, port, status in rows:
        # Step 2: don't touch anything a human marked "In Progress" - that's
        # a manual status this script should never override.
        if status == "In Progress":
            continue
        # Step 3: if this old finding didn't show up in the report we just
        # ingested, the rescan didn't find it anymore - mark it Remediated.
        if (nvt_oid, port) not in seen_nvt_oids_ports:
            conn.execute(
                "UPDATE findings SET status = 'Remediated', last_seen = ? WHERE id = ?",
                (now, finding_id),
            )


def summary(conn: sqlite3.Connection) -> List[tuple]:
    """Quick counts by status, for a sanity check after a run."""
    return conn.execute(
        "SELECT status, COUNT(*) FROM findings GROUP BY status ORDER BY status"
    ).fetchall()
