"""
Thin wrapper around python-gvm for pulling finished reports over GMP.

Requires the gvmd Unix socket to be reachable from wherever this runs -
see the compose.yaml change to bind-mount gvmd_socket_vol to a host path.
Verify the socket works with `gvm-cli` BEFORE debugging this module; if
gvm-cli can't reach it, neither can this.

Install: pip install --break-system-packages python-gvm
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple

from gvm.connections import UnixSocketConnection
from gvm.protocols.gmp import Gmp
from gvm.transforms import EtreeTransform

from . import config


def fetch_all_reports(since: str | None = None) -> List[Tuple[str, ET.Element]]:
    """
    Returns a list of (report_id, inner_report_element) tuples for every
    completed report gvmd knows about - full result sets, not the
    10-row-capped default a report remembers from its last GSA view.

    since: optional ISO8601 timestamp string. If given, only reports
    created after this time are fetched at all (cheaper than pulling
    full history every run). Pass db.get_last_run(conn) here.
    """
    # Step 1: build the filter string that decides WHICH reports to list.
    # rows=-1 means "don't cap the list," and if we were given a "since"
    # timestamp, only ask for reports created after that point.
    list_filter = "apply_overrides=0 rows=-1"
    if since:
        list_filter += f" created>{since}"

    # Step 2: set up the connection to gvmd over its local Unix socket, and
    # tell python-gvm to hand results back as parsed XML elements (Etree).
    connection = UnixSocketConnection(path=config.GVM_SOCKET_PATH)
    transform = EtreeTransform()

    results = []
    with Gmp(connection, transform=transform) as gmp:
        # Step 3: log in to gvmd using the credentials from config.py.
        gmp.authenticate(config.GVM_USERNAME, config.GVM_PASSWORD)

        # First: list which reports exist (this call's own filter doesn't
        # need to touch min_qod - it's just picking WHICH reports to look
        # at, not filtering their contents).
        listing = gmp.get_reports(filter_string=list_filter)

        # Step 4: pull just the report IDs out of that listing - we still
        # need to fetch each one individually to get its full contents.
        report_ids = [
            outer.get("id", "")
            for outer in listing.findall("report")
            if outer.get("id")
        ]

        # Then: pull each report's FULL result set individually. This is
        # the step that actually needs min_qod=0 and rows=-1 - confirmed
        # via gvm-cli that get_reports(details=True) alone silently
        # respects a report's last-viewed filter (often rows=10) unless
        # you override it explicitly per report.
        for report_id in report_ids:
            # Step 5: fetch this one report's full details, forcing no row
            # cap and no quality-of-detection filtering - without this, GVM
            # can silently hand back a trimmed-down result set.
            full = gmp.get_report(
                report_id=report_id,
                filter_string="apply_overrides=0 min_qod=0 rows=-1",
                details=True,
            )
            # Step 6: GMP wraps the real report in an extra outer <report>
            # envelope - unwrap it to get to the actual data (scan dates,
            # hosts, results) that parser.py expects.
            outer_report = full.find("report")
            if outer_report is None:
                continue
            inner_report = outer_report.find("report")
            if inner_report is None:
                continue
            results.append((report_id, inner_report))

    return results
