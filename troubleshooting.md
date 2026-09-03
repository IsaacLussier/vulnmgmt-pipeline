# Troubleshooting Log

Real problems hit while building this project, how they were diagnosed, and
what fixed them. The goal isn't a clean project — it's an honest record of
debugging, since that's what actually gets asked about in interviews.

---

## Template (copy this for new entries)

```markdown
## [Short description of the symptom]
**Symptom:** What was observed, as plainly as possible

**My initial guess:** What you thought was wrong before investigating

**Diagnostic steps:**
1. ...
2. ...
3. ...

**Root cause:** What was actually wrong

**Fix:** What resolved it

**What I'd check first next time:** The instinct/lesson to carry forward
```

---

## Network carrier flapping on enp1s0

**Symptom:** SSH connection from the Windows 10 desktop to the Dell Ubuntu
Server dropping intermittently, no obvious pattern.

**My initial guess:** Netplan misconfiguration on the server.

**Diagnostic steps:**
1. `networkctl status` — showed the interface cycling up and down
   (carrier loss/gain).
2. `journalctl -u systemd-networkd` — confirmed repeated carrier-loss events;
   config values weren't changing between drops, which pointed away from a
   config-level problem.
3. Checked the physical layer — traced the issue to a loose cable at the
   eero mesh node.

**Root cause:** Physical layer (loose cable), not a configuration issue.

**Fix:** Reseated the cable at the eero mesh node.

**What I'd check first next time:** Physical connectivity before assuming a
config problem. Config-level issues (netplan, systemd-networkd) tend to be
consistent and reproducible, not intermittent — intermittent symptoms point
toward hardware/physical layer first.

---

## Docker and libvirt iptables interference (flagged, not yet hit)

**Symptom:** Not yet encountered — flagged as a known quirk while confirming
Docker CE and KVM/libvirt could coexist on the same host.

**My initial guess:** N/A — noted preemptively.

**Diagnostic steps:** N/A yet.

**Root cause:** Docker and libvirt both manipulate iptables rules and can
interfere with each other's bridge networking.

**Fix:** N/A yet — noting this so if VM networking breaks after a Docker
restart/update, this is the first thing to check.

**What I'd check first next time:** If VM network connectivity breaks
unexpectedly after touching Docker, check iptables rules for
libvirt-managed chains before assuming a libvirt-only problem.

---

## [Next issue — add as it comes up]

**Symptom:**
**My initial guess:**
**Diagnostic steps:**
**Root cause:**
**Fix:**
**What I'd check first next time:**
