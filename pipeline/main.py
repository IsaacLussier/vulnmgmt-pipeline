"""
Entry point: pull every completed report from gvmd, parse it, and sync
the findings into the SQLite tracker, applying Open/In Progress/
Remediated status transitions along the way.

Run with:
    export GVM_SOCKET_PATH=/home/labuntuadmin/gvm-stack/sockets/gvmd/gvmd.sock
    export GVM_USERNAME=admin
    export GVM_PASSWORD=admin
    python3 main.py
"""

import sys
from datetime import datetime, timezone

from . import config
from . import db
from .gvm_client import fetch_all_reports
from .parser import parse_report, hosts_in_report


def run():
    # Step 1: bail out early with a clear message if login creds aren't set,
    # instead of failing later with a confusing connection error.
    if not config.GVM_USERNAME or not config.GVM_PASSWORD:
        print("GVM_USERNAME / GVM_PASSWORD not set - see the docstring at the top of main.py.")
        sys.exit(1)

    # Step 2: open (or create) the local SQLite tracker database.
    conn = db.connect(config.DB_PATH)

    # Step 3: remember "now" so we can save it as the new last-run time later,
    # and look up when the pipeline last ran so we only ask for newer reports.
    run_started_at = datetime.now(timezone.utc).isoformat()
    last_run = db.get_last_run(conn)

    # Step 4: ask gvmd (the scanner) for every completed report since last time.
    print(f"Connecting to gvmd via {config.GVM_SOCKET_PATH} ...")
    reports = fetch_all_reports(since=last_run)
    print(f"Found {len(reports)} report(s).")

    new_count = 0
    for report_id, report_elem in reports:
        # Step 5: skip reports we've already processed in a previous run.
        if db.already_ingested(conn, report_id):
            continue

        # Step 6: turn this report's raw XML into a simple list of Finding objects.
        new_count += 1
        findings = parse_report(report_elem, report_id)
        task_name = findings[0].task_name if findings else "unknown-task"

        # Step 7: save each finding into the DB, adding new ones and updating
        # ones we've seen before (this also reopens anything marked Remediated).
        print(f"  Ingesting report {report_id} ({task_name}) - {len(findings)} result(s)")
        db.upsert_findings(conn, findings)

        # Step 8: for every host this report actually scanned, close out any
        # tracked finding that didn't show up again - it must be fixed now.
        for host in hosts_in_report(report_elem):
            seen = {(f.nvt_oid, f.port) for f in findings if f.host == host}
            db.close_out_missing_findings(conn, host, seen)

        # Step 9: remember we've processed this report so we never redo it,
        # then save all of this report's changes to disk.
        db.mark_ingested(conn, report_id, task_name)
        conn.commit()

    # Step 10: print a quick summary of how many findings are in each status.
    print(f"\n{new_count} new report(s) ingested.")
    print("Status summary:")
    for status, count in db.summary(conn):
        print(f"  {status}: {count}")

    # Step 11: record this run's start time so the next run knows where to
    # pick up from, then close the database connection.
    db.set_last_run(conn, run_started_at)
    conn.close()


if __name__ == "__main__":
    run()