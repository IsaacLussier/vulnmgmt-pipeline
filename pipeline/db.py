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

from parser import Finding

SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nvt_oid TEXT NOT NULL,
    host TEXT NOT NULL,
    port TEXT NOT NULL,
    name TEXT NOT NULL,
    severity REAL NOT NULL,
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
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def already_ingested(conn: sqlite3.Connection, report_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM ingested_reports WHERE report_id = ?", (report_id,)
    ).fetchone()
    return row is not None


def mark_ingested(conn: sqlite3.Connection, report_id: str, task_name: str):
    conn.execute(
        "INSERT OR REPLACE INTO ingested_reports (report_id, task_name, ingested_at) "
        "VALUES (?, ?, ?)",
        (report_id, task_name, datetime.now(timezone.utc).isoformat()),
    )


def upsert_findings(conn: sqlite3.Connection, findings: Iterable[Finding]):
    """Insert new findings as 'Open', or update existing ones' last_seen /
    report info. If a finding was 'Remediated' and shows up again, it's
    reopened - a scanner seeing it again means it's back, regardless of
    what we thought before."""
    now = datetime.now(timezone.utc).isoformat()

    for f in findings:
        existing = conn.execute(
            "SELECT id, status FROM findings WHERE nvt_oid = ? AND host = ? AND port = ?",
            (f.nvt_oid, f.host, f.port),
        ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO findings
                   (nvt_oid, host, port, name, severity, threat, description,
                    status, task_name, report_id, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?)""",
                (f.nvt_oid, f.host, f.port, f.name, f.severity, f.threat,
                 f.description, f.task_name, f.report_id, now, now),
            )
        else:
            finding_id, status = existing
            new_status = "Open" if status == "Remediated" else status
            conn.execute(
                """UPDATE findings
                   SET last_seen = ?, task_name = ?, report_id = ?,
                       severity = ?, threat = ?, status = ?
                   WHERE id = ?""",
                (now, f.task_name, f.report_id, f.severity, f.threat,
                 new_status, finding_id),
            )


def close_out_missing_findings(conn: sqlite3.Connection, host: str,
                                 seen_nvt_oids_ports: set):
    """For a host that was just rescanned, mark anything not 'In Progress'
    and not present in seen_nvt_oids_ports (a set of (nvt_oid, port) tuples)
    as Remediated. Only call this for hosts that were actually covered by
    the report you just ingested - see hosts_in_report() in parser.py."""
    now = datetime.now(timezone.utc).isoformat()

    rows = conn.execute(
        "SELECT id, nvt_oid, port, status FROM findings WHERE host = ? AND status != 'Remediated'",
        (host,),
    ).fetchall()

    for finding_id, nvt_oid, port, status in rows:
        if status == "In Progress":
            continue
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
