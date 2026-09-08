# Decision Log

Why this project is built the way it is. Each entry captures a real choice made
along the way, the reasoning behind it, and what else was considered.

---

## Template (copy this for new entries)

```markdown
## [Short title of the decision]
**Decision:** What was chosen
**Why:** The reasoning, in your own words
**Alternative(s) considered:** What else was on the table, and why it lost out
```

---

## KVM vs VirtualBox for the lab host

**Decision:** KVM/QEMU (`qemu-system-x86`) on the headless Dell Ubuntu Server

**Why:** KVM is native to Linux and runs well on headless hardware with no GUI
overhead. It's also the hypervisor most enterprise Linux security
infrastructure actually uses, so it's more directly relevant experience than
VirtualBox.

**Alternative(s) considered:** VirtualBox — already in use on the ThinkPad for
Kali, but it's better suited to a desktop-with-GUI setup than a headless
server.

---

## Isolated virtual network for lab targets

**Decision:** A separate KVM virtual network with no route to the home LAN or
the internet, used only for Metasploitable2 and DVWA.

**Why:** Intentionally vulnerable machines shouldn't be reachable from the
home network or the wider internet. Keeping the lab network isolated means
mistakes or exploitation testing stay contained.

**Alternative(s) considered:** Running targets on the same bridged network as
other services (e.g. Plex) — rejected for obvious safety reasons; that
network config is planned separately, later, for non-lab services only.

---

## SQLite for the findings tracker

**Decision:** SQLite as the backing store for the vulnerability tracker

**Why:** No server process to install, configure, or keep running — the whole
database is a single file, which fits a project that gets started and stopped
on demand rather than run continuously. Python's standard library ships a
`sqlite3` module, so there's no extra dependency to manage. It's also trivial
to inspect directly (`sqlite3 vulnmgmt.db`, or a GUI browser) when
troubleshooting or demoing, without standing up a separate database server
just to look at the data.

**Alternative(s) considered:** Postgres/MySQL — better fit for concurrent
writers or a multi-user setup, but this tracker has exactly one writer
(the pipeline script) and one reader (you), so a server-based DB would add
setup and operational overhead with no real benefit at this scale.

---

## GMP API over manual XML export

**Decision:** Connect to gvmd directly via the Greenbone Management Protocol
(`python-gvm`), rather than manually exporting report XML from the GSA UI
and having the script read local files.

**Why:** The manual-export path is simpler — no auth, no connection code,
easy to test against any XML file — but it leaves a human step in the loop.
The project is explicitly meant to demonstrate Python automation of a
security task, and "click Export, then run the script" isn't quite that.
The GMP path gives a real end-to-end automated pull: connect, authenticate,
request every completed report, no clicking required.

**Alternative(s) considered:** A middle path — build and validate the parser
against manually-exported XML first, then add GMP later — was on the table,
since it would have let the parsing logic get tested independently of any
connection issues. Went straight for GMP instead, and used a synthetic XML
fixture (see `tests/fixtures/`) to validate the parser in isolation anyway,
getting a similar benefit without the two-phase detour.

---

## Exposing gvmd's Unix socket to the host

**Decision:** Modify `compose.yaml` so `gvmd_socket_vol` is bind-mounted to a
real host directory, instead of staying an internal Docker-managed volume.

**Why:** By default, GVM's official Compose stack keeps `gvmd.sock` in a
volume shared only between the `gvmd` and `gsad` containers — nothing
running as a normal host process (like this pipeline) can see it. Since the
pipeline runs directly on the lab host rather than inside the Docker
network, the socket has to be reachable from outside the containers.

**Alternative(s) considered:** Running the script inside a container
attached to the same Docker network/volume, the way Greenbone's own
`gvm-tools` container does it. This would avoid host-side file permission
quirks entirely, but adds more setup overhead than bind-mounting the volume
for this stage of the project. Worth revisiting if this becomes a scheduled
or production-style job rather than a manually-run script.

---

## `python-gvm >= 26.2.1` pin

**Decision:** `requirements.txt` pins `python-gvm>=26.2.1` rather than
leaving it unpinned or pinning one exact version.

**Why:** This gvmd install reports GMP protocol version 22.7. Older
`python-gvm` releases reject that outright with a `GvmError` — correct
detection of GMP 22.7 was only added in python-gvm 26.2.1. `>=` rather than
an exact pin, since the actual constraint is "new enough to know about
22.7," not one specific patch release.

**Alternative(s) considered:** An exact pin (`==26.9.1`, the version
actually installed and tested against) would be more strictly reproducible,
but reads as arbitrary six months from now with no explanation of *why*
that exact version. The `>=` form documents the real reason for the
constraint directly in the requirement itself.

---

## Finding identity: `(nvt_oid, host, port)`, not scoped by task

**Decision:** A finding's uniqueness in the tracker database is
`(nvt_oid, host, port)`. Which scan task discovered it is stored as metadata
on the row, but isn't part of what makes two findings the same or different.

**Why:** The same vulnerable service can legitimately be flagged by more
than one scan task against the same host — e.g. both an authenticated and
an unauthenticated scan of the same Metasploitable2 box finding the same
weak SSH config. That's genuinely one vulnerability, not two, and tracking
it as two separate rows would double-count severity and make "how many open
findings do we have" wrong.

**Alternative(s) considered:** Keying on `(nvt_oid, host, port, task_name)`
so each scan task tracks its own independent view — rejected because it
would mean the same real-world vulnerability shows up multiple times in
the tracker just because more than one scan type happened to catch it.

---

## Status transitions: host-scoped closing, manual "In Progress" is sticky

**Decision:** When a new report is ingested, findings are closed out
(marked `Remediated`) per **host**, not per **task** — any tracked,
non-`In Progress` finding on a host that was just rescanned and no longer
appears in the results gets marked `Remediated`. A `Remediated` finding that
reappears later is automatically reopened to `Open`. `In Progress` is a
manual status the ingestion logic never overwrites, regardless of whether
the finding shows up in a new scan or not.

**Why:** Closing based on task would mean a finding only closes if the
*exact same task* is rerun, but validating a fix only really requires that
the *host* was rescanned and the issue is gone — regardless of which named
task did the rescanning. Protecting `In Progress` from being silently
flipped by scan data keeps manual triage trustworthy — a finding you've
flagged as being actively worked on should only change status when you say
so, not because a scanner run happened to disagree.

**Alternative(s) considered:** Closing based on task match — rejected for
the reason above. Letting scan presence/absence override `In Progress`
automatically — rejected because it would undermine the point of having a
manual status at all.

---

## Idempotent ingestion via `ingested_reports`

**Decision:** A separate `ingested_reports` table records every report UUID
already processed; the pipeline skips any report already in that table.

**Why:** Without this, rerunning the pipeline against gvmd — after a crash,
or just by habit — would re-process reports it's already seen. Not
corrupting data outright (the upsert logic is safe either way), but making
`last_seen` timestamps and the remediation-closing logic fire on stale data
for no reason. Cheap to add, and it makes reruns a safe no-op.

**Alternative(s) considered:** None seriously — this was low-cost enough
that there wasn't a real tradeoff to weigh.

---

## Credentials and paths never in the repo

**Decision:** `GVM_SOCKET_PATH`, `GVM_USERNAME`, and `GVM_PASSWORD` are read
from environment variables, never hardcoded. Real values for local use live
in a gitignored `notes/` folder, not in tracked files.

**Why:** Standard practice worth actually demonstrating, not just stating —
this repo's history should never contain real credentials or internal IPs,
even for a low-stakes isolated lab, since the discipline itself is the
point.

**Alternative(s) considered:** A `.env` file loaded via `python-dotenv` —
functionally similar, just an extra dependency for something plain
`os.environ` already handles at this project's scale.

---

## Package structure: `pipeline/` with relative imports

**Decision:** The pipeline's modules live under a `pipeline/` package (with
an empty `pipeline/__init__.py`) rather than flat at the repo root, using
relative imports internally and run as `python3 -m pipeline.main` from the
repo root.

**Why:** A named package folder reads better in a portfolio repo than
several loose `.py` files sitting next to `README.md` and other top-level
docs. Relative imports plus the `-m` invocation are the correct way to make
that structure actually resolve, versus flat imports that only work when
every file sits in the same directory being run from.

**Alternative(s) considered:** Flat structure with all modules at the repo
root — simpler to run (`python3 main.py` directly), but reads as less
deliberate structurally, and was the original layout before deciding a
proper package was worth the small added friction.

---

## [Next decision — add as the project progresses]

**Decision:**
**Why:**
**Alternative(s) considered:**
