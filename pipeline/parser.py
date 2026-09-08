"""
Parses a GVM GMP <report> XML block into a flat list of Finding records.

GMP's report XML nests a <report> inside a <report> (the outer one is the
envelope with the id attribute, the inner one holds scan_start/scan_end/
results/hosts). This module expects the *inner* report element - see
gvm_client.py for where that unwrapping happens.

A couple of real quirks worth knowing before you trust this blindly against
your own gvmd's output:

- <host> elements contain the IP as text but also have nested <asset> and
  <hostname> children, so `host_elem.text` can come back with trailing
  whitespace/newlines. Always .strip() it.
- <severity> is occasionally absent on Log-level results. Falls back to 0.0.
- Field names have shifted across GMP protocol versions before. If this
  parser comes back with zero findings against a report you know has
  results, the first move is to dump one <result> block with
  ET.tostring(result, pretty_print) style output and diff it against what's
  assumed here - that's a TROUBLESHOOTING.md entry, not a bug in your head.
"""

from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET


@dataclass
class Finding:
    nvt_oid: str
    host: str
    port: str
    name: str
    severity: float
    threat: str
    description: str
    task_name: str
    report_id: str
    report_date: str  # scan_end, ISO8601 string as GMP returns it


def _text(elem, path, default=""):
    """Small helper: find a child by path, return stripped text or default."""
    child = elem.find(path)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def parse_report(report_elem: ET.Element, report_id: str) -> List[Finding]:
    """
    report_elem: the *inner* <report> element (the one with scan_start,
                 results, hosts as direct children).
    report_id: the report's UUID, passed in separately since the id lives
               as an attribute on the outer envelope, not this element.
    """
    task_name = _text(report_elem, "task/name", default="unknown-task")
    report_date = _text(report_elem, "scan_end", default="")

    findings = []
    for result in report_elem.findall("results/result"):
        name = _text(result, "name")
        host = _text(result, "host")
        port = _text(result, "port", default="general/tcp")
        threat = _text(result, "threat", default="Log")
        description = _text(result, "description")

        severity_text = _text(result, "severity", default="0.0")
        try:
            severity = float(severity_text)
        except ValueError:
            severity = 0.0

        nvt_elem = result.find("nvt")
        nvt_oid = nvt_elem.get("oid", "") if nvt_elem is not None else ""

        findings.append(Finding(
            nvt_oid=nvt_oid,
            host=host,
            port=port,
            name=name,
            severity=severity,
            threat=threat,
            description=description,
            task_name=task_name,
            report_id=report_id,
            report_date=report_date,
        ))

    return findings


def hosts_in_report(report_elem: ET.Element) -> List[str]:
    """Every host actually covered by this report, for the close-out logic
    in db.py - we only mark a finding Remediated if its host was actually
    rescanned, not just because it's missing from an unrelated report."""
    return [
        h.text.strip()
        for h in report_elem.findall("hosts/host")
        if h.text
    ]