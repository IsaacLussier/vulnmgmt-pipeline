# vulnmgmt-pipeline

A vulnerability management pipeline built to demonstrate skills for a Junior
Security Analyst role: scan orchestration with Greenbone/GVM, Python
automation of the vulnerability lifecycle, and (upcoming) hands-on web
application pentesting fundamentals against DVWA.

This is a self-directed lab project — not an assignment — built to freshen
up on Python and get hands-on with a real vulnerability management workflow
end to end: scan → parse → track → remediate → rescan.

## Architecture

```
vulnmgmt-pipeline/
├── pipeline/
│   ├── __init__.py
│   ├── config.py        # env-var based settings, no secrets in code
│   ├── gvm_client.py     # GMP connection + report retrieval
│   ├── parser.py         # raw GMP XML -> structured Finding records
│   ├── db.py              # SQLite schema + Open/In Progress/Remediated logic
│   └── main.py            # orchestration: fetch -> parse -> sync to DB
├── tests/
│   └── fixtures/
│       └── test_fixture.xml   # synthetic GMP report for testing parser.py
├── requirements.txt
├── .gitignore
├── DECISIONS.md
├── TROUBLESHOOTING.md
└── README.md
```

## Lab infrastructure

- **Lab host**: headless Dell Ubuntu Server, KVM/libvirt for VM targets,
  Docker Compose for the GVM stack.
- **Isolated scan network**: `isolated-lab` / `virbr-lab`, `192.168.100.0/24`
  — no route to the home LAN or internet, by design.
- **Targets**: Metasploitable2 (KVM VM, `.42`) and DVWA (Docker container via
  macvlan, `.43`).
- **Scanner**: Greenbone Community Edition (GVM), deployed via Docker
  Compose, started on-demand rather than run continuously.

## Connecting to GVM (GMP over Unix socket)

By default, the official GVM Docker Compose stack keeps `gvmd.sock` inside a
Docker-managed volume, not reachable from the host. To let this pipeline
connect via `python-gvm`, `gvmd_socket_vol` in `compose.yaml` is bind-mounted
to a host path instead:

```yaml
volumes:
  gvmd_socket_vol:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /home/labuntuadmin/gvm-stack/sockets/gvmd
```

Verify the socket is reachable before touching Python, using `gvm-cli`:

```bash
gvm-cli socket --socketpath ~/gvm-stack/sockets/gvmd/gvmd.sock --pretty --xml "<get_version/>"
```

## Setup

```bash
pip install --break-system-packages -r requirements.txt
```

`requirements.txt` pins `python-gvm>=26.2.1` — earlier versions reject GMP
22.7, which is what this gvmd install reports.

## Running the pipeline

Three environment variables are required. **Never commit real values** —
this repo's `.gitignore` excludes `notes/`, which is where actual
credentials and paths live locally, not here:

- `GVM_SOCKET_PATH` — path to the gvmd Unix socket on this host
- `GVM_USERNAME` — GMP username
- `GVM_PASSWORD` — GMP password

```bash
export GVM_SOCKET_PATH=/home/labuntuadmin/gvm-stack/sockets/gvmd/gvmd.sock
export GVM_USERNAME=<your-username>
export GVM_PASSWORD=<your-password>

cd ~/vulnmgmt-pipeline
python3 -m pipeline.main
```

(Or `source notes/set-env.sh` if you've saved these locally per the pattern
above, instead of re-typing the exports each session.)

This connects to gvmd over GMP, pulls every completed report, parses results
into `Finding` records, and syncs them into a local SQLite tracker
(`vulnmgmt.db`, gitignored) with `Open` / `In Progress` / `Remediated`
status tracking.

## Design notes

A finding's identity is `(nvt_oid, host, port)` — not which scan task found
it. The same vulnerable service flagged by both an authenticated and
unauthenticated scan of the same host is tracked as one row, not two.
`In Progress` is a manual status the ingestion logic never overwrites; a
finding only flips to `Remediated` when its host is rescanned and the
finding no longer appears. Full reasoning in `DECISIONS.md`.

## Usage reference

Run `python3 -m pipeline.main --help` or `python3 -m pipeline.main report --help`
for full usage at any time.

| Command | What it does |
|---|---|
| `python3 -m pipeline.main` | Fetch new completed reports from gvmd and sync findings into the tracker. Default command if none given. |
| `python3 -m pipeline.main ingest` | Same as above, explicit. |
| `python3 -m pipeline.main report` | Display all currently tracked findings. |

### `report` options

| Flag | Values | Default | Description |
|---|---|---|---|
| `--task` | any task name, e.g. `DVWA` | none (all tasks) | Filter to one scan task. Must match exactly - check real names with `sqlite3 vulnmgmt.db "SELECT DISTINCT task_name FROM findings;"` |
| `--sort` | `severity`, `qod` | `severity` | Sort output by CVSS severity or Quality of Detection |

### Examples

    python3 -m pipeline.main report
    python3 -m pipeline.main report --task DVWA
    python3 -m pipeline.main report --sort qod
    python3 -m pipeline.main report --task "Metasploitable2-Auth" --sort qod

## Status

- [x] Lab infrastructure (isolated network, Metasploitable2, DVWA)
- [x] GVM scanner deployed, initial scans run against both targets
- [x] GMP socket exposed to host, connection validated
- [x] Pipeline running end-to-end against live scan data
- [ ] Manual remediation + rescan to validate status-closing logic
- [ ] Documentation polish for portfolio presentation
