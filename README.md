# Vulnerability Management Mini-Pipeline

A home-lab project that builds a complete, working vulnerability management lifecycle — scan, ingest, track, remediate, rescan — using open-source tools and a Python automation layer.

## Goal

Most portfolio projects stop at "I ran a vulnerability scanner." This project goes a step further: it closes the loop. Findings are scanned, parsed into a tracker, triaged by severity, actually remediated on the target systems, and then re-scanned to confirm the fix worked. That lifecycle — not just the scan — is what a junior security analyst is actually expected to support day to day.

## Architecture

*(Diagram goes here — sketch the lab topology in draw.io/excalidraw and embed the PNG.)*

- **Host:** Dell Ubuntu Server, running KVM/libvirt for virtualization
- **Scanner:** Greenbone/OpenVAS Community Edition (VM)
- **Vulnerable targets:**
  - Metasploitable2 (VM) — intentionally vulnerable Linux host
  - DVWA (Docker container) — intentionally vulnerable web application
- **Attacker/analyst workstation:** ThinkPad running Kali Linux (VM), used for manual pentesting and running scans
- **Network:** All lab VMs isolated on an internal virtual network, not bridged to the home LAN

## What this project demonstrates

- **Vulnerability management lifecycle** — identifying, tracking, and remediating findings end to end, not just a one-time scan
- **Python automation of security tasks** — a script that parses raw scanner output (XML) and loads it into a structured tracker
- **Log/report analysis** — reading and interpreting scanner and system output to prioritize real risk
- **Basic web application security fundamentals** — hands-on exploitation of SQL injection, XSS, and CSRF in a safe, isolated environment
- **Practical Linux systems administration** — including troubleshooting real infrastructure issues along the way (see Lessons Learned)

## Tools used

| Purpose | Tool |
|---|---|
| Hypervisor | KVM / libvirt |
| Vulnerability scanner | Greenbone (OpenVAS) Community Edition |
| Vulnerable Linux target | Metasploitable2 |
| Vulnerable web app | DVWA (Docker) |
| Pentesting toolkit | Kali Linux |
| Automation / parsing | Python 3 |
| Tracking | SQLite |

## Repository structure

```
vulnmgmt-pipeline/
├── README.md
├── LICENSE
├── requirements.txt
├── scripts/
│   └── ingest_findings.py      # Parses OpenVAS export, loads into tracker
├── docs/
│   ├── architecture-diagram.png
│   └── screenshots/
│       ├── scan-results.png
│       ├── tracker-before.png
│       ├── tracker-after.png
│       └── dvwa-sqli.png
└── writeups/
    └── dvwa-manual-pentest.md   # Notes on SQLi/XSS/CSRF exercises
```

## How it works

1. OpenVAS scans the two target systems (Metasploitable2, DVWA)
2. Scan results are exported as XML
3. `ingest_findings.py` parses the export, extracts CVE/CVSS/severity, dedupes entries, and loads them into a SQLite tracker with status: `Open` → `In Progress` → `Remediated`
4. Selected findings are manually remediated on the target systems
5. A rescan confirms the fix, and the tracker is updated to reflect the new status

## Results

*(Fill in once complete — e.g. "Initial scan surfaced X findings across Y severity levels. Y of them were remediated and confirmed via rescan.")*

## Lessons learned

- Diagnosed a flapping physical network link (cable/port issue on the lab host) using `networkctl status` and `journalctl -u systemd-networkd` rather than assuming a config problem — netplan's DHCP config was correct the whole time; the issue was physical layer.
- *(Add more as you go — e.g. XML parsing quirks, OpenVAS feed sync issues, Docker/libvirt bridging notes.)*

## Setup / reproduction

```bash
# Install dependencies
pip install -r requirements.txt

# Run the ingestion script against an OpenVAS export
python3 scripts/ingest_findings.py --input scan_export.xml --db tracker.db
```

## License

MIT — see [LICENSE](LICENSE) for details.
