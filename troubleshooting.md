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

## Metasploitable2 VM boots but has no network interface

**Symptom:** VM shows running, but ip link show inside the guest only shows loopback — no eth0 at all. virsh net-dhcp-leases stays empty.

**My initial guess:** DHCP misconfiguration inside the guest (eth0 set to manual instead of auto).

**Diagnostic steps:** 
1. Confirmed the VM was actually alive and not hung using virsh domstats metasploitable2 --cpu-total, checked twice a few seconds apart — small but nonzero delta in CPU time confirmed it was up and idle, not crashed
2. Since the default serial console (--console pty,target_type=serial) showed nothing (Metasploitable2 was never built to output over serial), set up a VNC console instead — connected via virsh vncdisplay, SSH-tunneled the port to a Windows PC, and viewed the boot process visually with TightVNC Viewer
3. Logged in via VNC (msfadmin/msfadmin) and ran ip link show / ifconfig -a directly inside the guest — confirmed eth0 wasn't just unconfigured, it didn't exist as a device at all, ruling out a simple DHCP/config issue

**Root cause:** virt-install defaulted to a modern NIC model (e1000e). Metasploitable2's 2008-era 2.6.24 kernel has no driver for it, so no network hardware was ever detected.

**Fix:** virsh edit metasploitable2, changed <model type='e1000e'/> to <model type='rtl8139'/> — an old, universally-supported NIC model with a built-in kernel driver. Hard-reset (virsh destroy + virsh start) and eth0 appeared immediately with a working DHCP lease.

**What I'd check first next time:** For legacy VM images, explicitly set NIC model to something period-appropriate (rtl8139/e1000) at creation time instead of trusting modern defaults.

---

## No output on serial console for legacy VM

**Symptom:** virsh console metasploitable2 connected successfully but showed a completely blank screen — no boot output, no login prompt.

**My initial guess:** VM was hung or stuck mid-boot.

**Diagnostic steps:** Checked virsh domstats --cpu-total twice, a few seconds apart — small nonzero CPU delta confirmed the VM was alive and idle, not crashed or looping.

**Root cause:** Metasploitable2 was built for VMware and never configured to output over a serial port (ttyS0) — it only knows how to render to a legacy VGA-style display, so nothing was ever sent to the serial console we attached.

**Fix:** Recreated the VM with --graphics vnc,listen=0.0.0.0 instead of the serial console, SSH-tunneled the VNC port to the Windows PC, and viewed it with TightVNC Viewer — showed the real boot screen and login prompt immediately.

**What I'd check first next time:** For old/legacy disk images, default to VNC graphics rather than serial console from the start — serial only works reliably on images built with cloud-init/modern console expectations.

---

## Modern SSH client refuses to connect to legacy SSH server

**Symptom:** ssh msfadmin@192.168.100.42 fails with Unable to negotiate... no matching host key type found. Their offer: ssh-rsa,ssh-dss.

**My initial guess:** Assumed it was a networking or auth issue.

**Diagnostic steps:** Error message directly named the mismatch — client and server couldn't agree on a host key algorithm.

**Root cause:** Metasploitable2's ancient SSH server only supports ssh-rsa/ssh-dss host keys. Modern OpenSSH clients (Ubuntu 26.04's included) disabled ssh-rsa by default and fully removed ssh-dss support entirely, since both are considered cryptographically weak by current standards.

**Fix:** Explicitly re-enabled the older algorithm for this one connection: ssh -oHostKeyAlgorithms=+ssh-rsa msfadmin@192.168.100.42.

**What I'd check first next time:** When connecting to any old/legacy Linux box, expect modern SSH clients to reject outdated host key types by default — -oHostKeyAlgorithms=+ssh-rsa is a fast, standard workaround.


## Scans completing instantly with zero findings across all targets

**Symptom:** 
- All three scan tasks (DVWA, Metasploitable2-Authenticated,
  Metasploitable2-Unauth) moved from `New` → `Done` in a matter of seconds,
  rather than the many minutes expected for a `Full and fast` scan.
- Every report showed `0` across every severity column (Critical, High,
  Medium, Low, Log, False Positive) — not just an "N/A" summary tile, but
  literal zero results on every row.
- This was true even against Metasploitable2, a target known to be
  extremely vulnerable — a genuinely clean scan result against that host
  was implausible on its face.
- No errors surfaced anywhere in the GSA UI itself; tasks reported `Done`
  with no failure indicator, making the problem easy to miss at a glance.

**My initial guess:** Feed data hadn't fully synced — GVM's gvmd logs had earlier shown "No SCAP database found" / "No CERT database found" during initial setup, so the first assumption was that the vulnerability test feed was incomplete and scans were running against an empty ruleset.

**Diagnostic steps:** 
- Confirmed the NVT feed had actually updated cleanly (`Updated NVT cache
  from version 0 to 202609030608`) and SCAP data had copied through current
  year CVEs — feed was not the problem.
- Checked `docker compose ps -a` and found nine containers, including the
  scanner engine (`openvas`) and the web UI (`gsa`), sitting in `Exited (137)`
  — same exit code, same relative timestamp, across unrelated containers.
  Initially suspected an OOM kill, but the real cause was simpler: the Dell
  host had lost power (found unplugged) roughly 22 hours earlier. Docker
  Compose's data-loader containers exit by design after copying feed data,
  so a dead container wasn't visually distinguishable from a normal
  "finished successfully" one at a glance — worth remembering for next time.
- Brought the stack back up with `docker compose up -d` and confirmed
  `openvas`/`gsa` returned to a running state.
- Relaunched a scan. It still completed in seconds with zero results, on a
  target (Metasploitable2) that should never scan clean. That ruled out
  "GVM just needed a restart" as the full explanation.
- Inspected the scanner container's actual network attachment:
  `docker inspect <container> | grep -A20 "Networks"` showed `ospd-openvas`
  and `openvas` both living only on the Compose-created default bridge
  (`172.18.0.0/16`) — with zero route to `isolated-lab`/`virbr-lab`
  (`192.168.100.0/24`), where both scan targets actually live. Docker
  Compose creates an isolated project network by default; nothing in the
  original setup had ever explicitly attached the scanner containers to the
  lab network. Confirmed via `/proc/net/route` inside the container: only a
  default route out the Compose bridge, nothing pointing at `.100.0/24`.

**Root cause:** Two independent problems stacked on top of each other:
1. The scanner containers were never network-connected to `isolated-lab`
     in the first place — a gap from initial setup, not something that
     broke later.
2. Separately, the Metasploitable2 VM had not survived a power outage —
     `virsh list --all` showed it `shut off`, meaning even a correctly
     networked scanner would have had nothing to reach against that
     specific target. (DVWA, running as a Docker container rather than a
     VM, had also silently died in the same outage and needed its own
     restart — it just hadn't been checked yet at that point.)

**Fix:** 
  - Attached both scanner containers to the same macvlan network already
    built for DVWA, giving them real interfaces on `192.168.100.0/24`:
    `docker network connect --ip 192.168.100.50 isolated-lab-macvlan
    ospd-openvas` (and the same for `openvas` on `.51`).
  - Restarted the Metasploitable2 VM: `virsh start metasploitable2`.
  - Restarted DVWA and set a persistent restart policy so a future power
    event doesn't silently take it down again:
    `docker start dvwa && docker update --restart unless-stopped dvwa`.
  - Confirmed the fix with a live packet capture on the target-side network
    (`tcpdump` on `virbr-lab`) while re-triggering a scan, and watched
    traffic actually arrive from the new scanner IPs — rather than trusting
    the GSA UI alone, since it had already reported false "success" once.

**What I'd check first next time:** A scan that finishes in a few seconds with zero
findings against a target known to be vulnerable is never a clean result. Treat it as a signal the scan never actually reached the target, not as "nothing was found."



##  Corrupted status/description from misaligned INSERT

**Symptom:** Pipeline ran clean (exit 0), but report command printed raw scan text instead of status words.

**Guesses that were wrong:** stray debug print, terminal scrollback, shadowed import. Ruled all out with grep and a direct file redirect.

**Root cause:** upsert_findings()'s INSERT had 13 columns but only 12 ? placeholders - 'Open' was hardcoded in the middle of VALUES, pushing every value after it one column late. description's text landed in status; no error, since both are TEXT.

**Fix:** Added the missing ? before 'Open'. Had to delete and rebuild vulnmgmt.db since existing rows were already corrupted.

**Lesson:** Count placeholders against columns when mixing literals into VALUES - or just parameterize everything, always. Clean exit code ≠ correct data; caught this via a second read path (report), not an error.
