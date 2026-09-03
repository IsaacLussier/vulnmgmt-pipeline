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

**Why:** [fill in — e.g. no server setup needed, easy to inspect/query
directly, appropriate for the scale of a lab project]

**Alternative(s) considered:** [fill in]

---

## [Next decision — add as the project progresses]

**Decision:**
**Why:**
**Alternative(s) considered:**
