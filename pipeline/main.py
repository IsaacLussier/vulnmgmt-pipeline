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
    if not config.GVM_USERNAME or not config.GVM_PASSWORD:
        print("GVM_USERNAME / GVM_PASSWORD not set - see the docstring at the top of main.py.")
        sys.exit(1)

    conn = db.connect(config.DB_PATH)

    run_started_at = datetime.now(timezone.utc).isoformat()
    last_run = db.get_last_run(conn)

    print(f"Connecting to gvmd via {config.GVM_SOCKET_PATH} ...")
    reports = fetch_all_reports(since=last_run)
    print(f"Found {len(reports)} report(s).")

    new_count = 0
    for report_id, report_elem in reports:
        if db.already_ingested(conn, report_id):
            continue

        new_count += 1
        findings = parse_report(report_elem, report_id)
        task_name = findings[0].task_name if findings else "unknown-task"

        print(f"  Ingesting report {report_id} ({task_name}) - {len(findings)} result(s)")
        db.upsert_findings(conn, findings)

        for host in hosts_in_report(report_elem):
            seen = {(f.nvt_oid, f.port) for f in findings if f.host == host}
            db.close_out_missing_findings(conn, host, seen)

        db.mark_ingested(conn, report_id, task_name)
        conn.commit()

    print(f"\n{new_count} new report(s) ingested.")
    print("Status summary:")
    for status, count in db.summary(conn):
        print(f"  {status}: {count}")

    db.set_last_run(conn, run_started_at)
    conn.close()


if __name__ == "__main__":
    run()