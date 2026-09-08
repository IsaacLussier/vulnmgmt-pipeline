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


def fetch_all_reports() -> List[Tuple[str, ET.Element]]:
    """
    Returns a list of (report_id, inner_report_element) tuples for every
    completed report gvmd knows about. The "inner report element" is the
    one parser.py expects - see the unwrapping below, since GMP nests
    <report><report>...</report></report>.
    """
    connection = UnixSocketConnection(path=config.GVM_SOCKET_PATH)
    transform = EtreeTransform()

    results = []
    with Gmp(connection, transform=transform) as gmp:
        gmp.authenticate(config.GVM_USERNAME, config.GVM_PASSWORD)

        # details=True is what actually populates <results> - without it
        # you get report metadata with no findings, which looks like a
        # parser bug but isn't.
        response = gmp.get_reports(details=True)

        for outer_report in response.findall("report"):
            report_id = outer_report.get("id", "")
            inner_report = outer_report.find("report")
            if inner_report is None:
                continue
            results.append((report_id, inner_report))

    return results
