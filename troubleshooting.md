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

## [Metasploitable2 VM boots but has no network interface]

**Symptom:** VM shows as running in virsh list --all, but inside the guest, eth0 doesn't exist at all — ip link show and ifconfig -a only show the loopback interface. virsh net-dhcp-leases isolated-lab stays empty since the guest never even attempts a DHCP request.
**My initial guess:** Assumed it was a DHCP configuration issue inside the guest (e.g., eth0 set to manual instead of auto in /etc/network/interfaces), since that's the more common cause of "no IP" problems.
**Diagnostic steps:** 
1. Confirmed the VM was actually alive and not hung using virsh domstats metasploitable2 --cpu-total, checked twice a few seconds apart — small but nonzero delta in CPU time confirmed it was up and idle, not crashed
2. Since the default serial console (--console pty,target_type=serial) showed nothing (Metasploitable2 was never built to output over serial), set up a VNC console instead — connected via virsh vncdisplay, SSH-tunneled the port to a Windows PC, and viewed the boot process visually with TightVNC Viewer
3. Logged in via VNC (msfadmin/msfadmin) and ran ip link show / ifconfig -a directly inside the guest — confirmed eth0 wasn't just unconfigured, it didn't exist as a device at all, ruling out a simple DHCP/config issue
**Root cause:** libvirt's virt-install defaulted to emulating a modern NIC model (e1000e) for the VM's network interface. Metasploitable2's 2.6.24 kernel (released 2008) predates driver support for that NIC model, so the guest kernel never detected any network hardware at all — not a networking misconfiguration, but a driver/hardware-emulation mismatch.
**Fix:** Edited the VM's XML definition (virsh edit metasploitable2) and changed the interface's <model type='...'/> from e1000e to rtl8139 — a much older, universally-supported NIC model that this kernel has a built-in driver for. After a hard power-off (virsh destroy, since graceful virsh shutdown never completed — likely acpid isn't configured in this old image) and restart, eth0 appeared immediately and picked up a DHCP lease from isolated-lab.
**What I'd check first next time:** When working with any old/legacy VM image, explicitly set the NIC model to something period-appropriate (rtl8139 or e1000, not e1000e or virtio) at VM creation time, rather than relying on virt-install's modern defaults — would have skipped this entire troubleshooting cycle.

---

## [Next issue — add as it comes up]

**Symptom:**
**My initial guess:**
**Diagnostic steps:**
**Root cause:**
**Fix:**
**What I'd check first next time:**
