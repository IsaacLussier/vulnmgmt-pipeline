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

## [Next issue — add as it comes up]

**Symptom:**
**My initial guess:**
**Diagnostic steps:**
**Root cause:**
**Fix:**
**What I'd check first next time:**
