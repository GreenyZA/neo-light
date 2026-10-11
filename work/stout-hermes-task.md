# HERMES / free-agent task: Stout VM farm (not the live OS)

Feed this whole file to Hermes (`neo`) or Light Engine. Do not invent steps. Do not "fix" the host. If a check fails, write `~/Projects/stout/FAILED.md` and **stop**.

You are not James. Never SuperGrok. Never Ultra.

---

## 0. What this project is (read before any command)

**Stout Linux** is a new personal OS WarPuppy is building with James. It is **not** installed yet. It must **not** replace or rebrand the machines you are sitting on.

Today's live systems (leave them alone except the whitelist in §5):

| Role | Alias | Hostname | IPv4 | OS now | User |
|------|-------|----------|------|--------|------|
| Daily driver (hearth) | hearth | `acer` | `192.168.1.10/24` | Arch rolling. **Not Omarchy.** GPU (RX 480 4 GB), llama, Grafana, wiki. | `warpuppy` (uid 1000) |
| Helper (anvil) | anvil | `Lenovo` | `192.168.1.8/24` | **Omarchy** (Arch-like) 4.x. Helper, NFS, bar. | `warpuppy` (uid 1000) |

Gateway `192.168.1.1`. LAN `192.168.1.0/24`.

**Twinforge** is the current two-node shop floor (those two boxes). Later Twinforge *becomes* Stout (plan G6). Not today. Do not rename hosts. Do not change IPs. Do not write Stout into the live `/etc/os-release`.

Stout product facts (for the VMs you will create, not the host):

- Name: **Stout**. Product `Stout Linux`. ID `stout`. Compound `stout-linux`.
- Author face: WarPuppy. Not GreenyZA on anything public. Not Clarity (Clarity is the business).
- Mascot: a **stoat** (the animal). Tiny but fierce. Spelling of the animal is stoat. Distro string is Stout (he accepted beer/CLI name collisions).
- Vibe: bare bones, just works, nothing included, you add it. If it is not built, you build it.
- Base ISO (later): kernel, systemd, pacman, network, nftables drop. No Hyprland on the base.
- Workstation edition later packages today's Twinforge (Hyprland, Quickshell bar, helper).
- **Ermine** = hardening profile (UKI, Secure Boot, signed repo, no AUR). Not today.
- Build path: **not** Linux From Scratch as the product. Optional LFS VM is school only. Product is a minimal **Arch ISO** (`archiso`) with our `os-release` and repo.
- Look: sand `#C49A6C` cream `#F4EFE6` ink `#1C1916` tail-tip `#111111`. Hardening UI is ermine white `#F6F4EF` plus black tip. Not Kali. Not Omarchy candy.
- Code home: `~/Projects/stout/` (this is a git/project tree, **not** an installed OS).
- Plan: `~/Documents/Clarity/01-Projects/Personal-OS/PLAN.md`

**This task (only this):**

1. Keep Stout **separate** from the live OS.
2. On **Lenovo only**, install QEMU + libvirt + Cockpit so VMs are managed in a browser. Multiple VMs allowed. Small RAM.
3. Scaffold `~/Projects/stout/` if missing.
4. Put VM disks on **Lenovo local disk**, never NFS.
5. **Stop.** Do not build the ISO. Do not pacstrap the host. Do not cut over.

CHG: `CHG-2026-023`. Log result in `~/Projects/stout/DONE.md` or `FAILED.md`.

---

## 1. Login and SSH (no passwords in this file)

There is **no password here**. Key login. User is always `warpuppy`. Do not `su` to a different user. Do not create users. Do not change passwords. Do not copy keys. Do not log into GoDaddy, Gmail, or GitHub as a new identity.

| From | To | Command |
|------|----|---------|
| Lenovo (you are often here) | local | you are already `warpuppy@Lenovo` |
| Lenovo | acer | `ssh -o BatchMode=yes -o ConnectTimeout=5 server` or `ssh -o BatchMode=yes warpuppy@192.168.1.10` |
| acer | Lenovo | `ssh -o BatchMode=yes -o ConnectTimeout=5 warpuppy@192.168.1.8` |
| anyone | acer | `ssh server` is the locked alias for `192.168.1.10` |

`sudo` is NOPASSWD on both boxes. That is a loaded gun. You may only sudo the exact commands in §5. If sudo asks for a password, **stop**.

Cockpit URL after success: `https://192.168.1.8:9090`  
Login: Linux user `warpuppy` (same account, PAM). Self-signed cert: expected. LAN only.

NICs (do not reconfigure):

- acer `enp1s0` MAC `98:ee:cb:63:57:be`
- Lenovo `enp0s31f6` MAC `6c:4b:90:7f:49:bf`

Do not set Lenovo to `.11`. Do not `hostnamectl`.

---

## 2. HARD WALL (this is how you do not break the live OS)

The live OS is Omarchy on Lenovo and Arch on acer. **Stout is a project + VMs.** If you install Stout onto `/` you have failed.

### Never (any host)

- `pacman -Syu` / `-Syy` / `-Syyu` (no world upgrade)
- `pacman -R` / `-Rns` / `-Rsc` except the backout script
- `pacstrap` to `/` or to any real partition
- `mkfs`, `wipefs`, `dd` to `/dev/sd*` `/dev/nvme*` `/dev/vd*` `/dev/mapper*`
- `parted`, `fdisk`, `sgdisk`, `lvcreate` on real disks
- `hostnamectl`
- Edit `/etc/os-release`, `/etc/pacman.conf`, `/etc/fstab`, `/etc/hosts` (except you do **not** touch them)
- Anything under `/usr/share/omarchy/`
- Hyprland / Omarchy / waybar / `~/.config/hypr` / `~/.config/omarchy`
- Docker, Portainer, Grafana, Prometheus, llama, Ollama, wiki
- Install any LLM on Lenovo
- `ufw reset` / disable ufw / allow 9090 from `any`
- `systemctl isolate`, reboot, shutdown, `poweroff`
- `chown -R`, `chmod -R` on `/` or `$HOME`
- git push, gh, public remotes
- Change IP, NIC, NetworkManager connections
- Nested "I'll just fix omarchy first"

### Stout vs host

| Stout (allowed) | Live OS (forbidden to become Stout) |
|-----------------|--------------------------------------|
| `~/Projects/stout/` files | `/` on acer or Lenovo |
| qcow2 under `/home/warpuppy/stout-vms/` on Lenovo **local** disk | NFS `~/Projects` used as VM disks |
| VM guest `os-release` ID=stout | host `os-release` |
| Cockpit manages **qemu VMs** | Cockpit used to reinstall the host |

If `findmnt -n -o FSTYPE /home/warpuppy` is `nfs` or `nfs4`, **stop**. VM disks cannot live there.

If `/etc/os-release` on the **host** already says `ID=stout`, **stop** and write FAILED.md (host was already damaged).

---

## 3. Where to run

Virt stack: **Lenovo only** (`192.168.1.8`, hostname `Lenovo`).

```
h=$(tr -d ' \n' </etc/hostname)
```

- If `$h` is `Lenovo`: run scripts locally.
- If `$h` is `acer`: `ssh -o BatchMode=yes warpuppy@192.168.1.8` and run the same scripts there. Do not install qemu on acer in this task.
- Any other hostname: **stop**.

ISO build (acer, 8 threads) is a **later** task. Not this file.

RAM on Lenovo is ~15 GiB and the desktop is already using a lot. Cap: **at most two VMs**, **3072 MiB RAM each**, **2 vCPUs each**. Do not start them in this task unless smoke needs one stopped empty domain.

---

## 4. Files you may write

Only these paths:

- `~/Projects/stout/**` (project; this may be NFS; source only)
- `/home/warpuppy/stout-vms/` on Lenovo if `$HOME` is **not** NFS (qcow2 + README)
- `~/Projects/stout/DONE.md` or `FAILED.md`

Scripts live in `~/Projects/stout/scripts/`. Prefer **running the scripts** over typing your own shell.

---

## 5. Do this in order (or run the scripts)

From `~/Projects/stout` on Lenovo:

```
bash scripts/00-preflight.sh
bash scripts/01-install-lenovo-virt.sh
bash scripts/02-smoke.sh
```

If a script exits non-zero: **stop**. Do not continue. Do not patch the script unless it is a missing package **name** already listed. Write FAILED.md with the last 50 lines of output.

### Package whitelist (Lenovo, `--needed` only, never `-Syu`)

```
qemu-desktop libvirt virt-install cockpit cockpit-machines dnsmasq edk2-ovmf iptables-nft dmidecode
```

Optional if the first list cannot satisfy deps (install only what pacman says is required, still no `-Syu`):

```
qemu-system-x86 qemu-img
```

### Units whitelist

```
sudo systemctl enable --now libvirtd.socket
sudo systemctl enable --now cockpit.socket
sudo virsh net-start default || true
sudo virsh net-autostart default
sudo usermod -aG libvirt,kvm warpuppy
```

Do not restart NetworkManager. Do not reboot for the group; Cockpit/libvirt system session does not need your current shell group for `qemu:///system`.

### Firewall whitelist (only if `ufw` is active)

```
sudo ufw allow from 192.168.1.0/24 to any port 9090 proto tcp comment stout-cockpit
sudo ufw status
```

Do not `ufw allow 9090` without the source net.

### Libvirt storage

Pool `stout-vms` → `/home/warpuppy/stout-vms` (local). Do not use `/var/lib/libvirt/images` for Stout if you can set the pool. Do not put qcow2 in `~/Projects`.

---

## 6. Scaffold if missing (files only)

If `~/Projects/stout/README.md` is missing, create the tree from `~/Documents/Clarity/01-Projects/Personal-OS/PLAN.md` section "Scaffold". ISO `os-release` belongs in `iso/airootfs/etc/os-release` **inside the project**, never `/etc/os-release` on the host.

Do not `cp -a /usr/share/archiso` until a later task that installs `archiso` on **acer**. This task does not install `archiso`.

---

## 7. Smoke (must all pass)

On Lenovo:

- `test -e /dev/kvm`
- `systemctl is-active libvirtd.socket` or `libvirtd` is active
- `systemctl is-active cockpit.socket`
- `virsh list --all` works (sudo or qemu:///system)
- `ss -lntp | grep 9090` listens
- `curl -k -sS -o /dev/null -w '%{http_code}\n' https://127.0.0.1:9090/` is `200` or `301` or `302`
- `grep '^ID=' /etc/os-release` on the **host** is still `arch` or omarchy-like, **not** `stout`
- `hostname` still `Lenovo`

From acer (optional): browser `https://192.168.1.8:9090` as `warpuppy`.

Write `~/Projects/stout/DONE.md` with: packages installed, cockpit URL, pool path, `df -h /home/warpuppy`, host `ID=` line, and "live OS unchanged".

---

## 8. Backout (if you broke enablement only)

```
bash ~/Projects/stout/scripts/backout-lenovo-virt.sh
```

That script may disable cockpit.socket and libvirtd **only if this task enabled them**. It must not `pacman -Rns` unless DONE.md says the packages were newly installed **and** WarPuppy said backout. Default backout = stop/disable cockpit.socket, leave qemu packages (safe).

---

## 9. After this task

**Stop.** Next job (not you unless a new file says so): archiso on **acer**, G2 ISO, boot that ISO **inside** a Stout VM. Never on the Lenovo root.

---

## 10. Report

One of:

- `DONE.md` as in §7
- `FAILED.md`: command, exit code, why you stopped, host still not Stout
