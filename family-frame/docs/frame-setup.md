# Putting the dashboard on an AiMOR PF1007L frame

These are working notes from one AiMOR PF1007L (Allwinner A33, Android 6.0.1, firmware
`321-OS-AIMOR.0.20260416`). The authoritative guide is
[wesbos/photo-frame-dashboard](https://github.com/wesbos/photo-frame-dashboard). Read its
"For agents: start here" section and the device doc for your frame first. Firmware variants
change often, so check that repo's newest issues before each step.

## Rules that apply to every step

- Make a verified backup before any write: byte count, SHA-256, gzip readback.
- Make one change at a time, and record how to undo it first.
- Pin every download by SHA-256 from an official source.
- Keep flash dumps private. They hold Wi-Fi passwords, tokens, serial numbers and MAC addresses.
- Stop at the first mismatch in a hash, model string, offset or size.

## 1. Keep the frame away from the vendor server

The AiMOR launcher keeps an unencrypted TCP connection to the vendor server on port 7806.
That server can run any command as root on the frame. Keep the frame off Wi-Fi until the
vendor domain is blocked on your DNS server (for example a Pi-hole):

```
pihole --regex '(^|\.)efercro\.com$' --comment 'AiMOR vendor'
```

A DNS block does not stop a hard-coded IP address. Block outbound TCP 7806 on your router too.

## 2. Root ADB with no SD card (route T3c)

T3c gets root ADB over Wi-Fi. Your PC acts as the vendor server for a few minutes and sends
one root command. Nothing is written to flash. Upstream doc:
`docs/pf1007l-20260410-network-adb.md` in the wesbos repo.

1. Back up your Pi-hole config (`pihole.toml` and `gravity.db`).
2. Point the one command host at your PC. Keep the rest of the domain blocked:
   - `pihole allow imsconnect.efercro.com`
   - `pihole-FTL --config dns.hosts '["<pc-ip> imsconnect.efercro.com"]'`
   - `pihole reloaddns`
3. Check with `nslookup`: `imsconnect.efercro.com` gives your PC's IP, and
   `www.efercro.com` gives `0.0.0.0`.
4. Allow inbound TCP 7806 from your LAN on the PC firewall.
5. Connect the frame to Wi-Fi. Read its IP in Settings > About > Status.
6. Run the repo's `server.py --bind <pc-ip> --frame-ip <frame-ip> --seconds 600`.
   600 is the maximum. AiMOR retries on its own, so the frame usually logs in within seconds.
7. `adb connect <frame-ip>:5555`. Check that `id` shows uid=0.
8. Back up every partition over ADB. Read each one twice and accept it only when both
   SHA-256 values match and the size matches `/proc/partitions`. Run binary redirects from
   bash or cmd.exe. PowerShell 5 `>` corrupts binary output.
9. Make USB ADB persistent: `setprop persist.sys.usb.config mass_storage,adb`.
   Undo: `setprop persist.sys.usb.config mass_storage`.
10. Remove the `dns.hosts` and allow entries. Keep the domain block. Remove the firewall rule.

Pitfalls:

- In Pi-hole v6 a regex block wins over a `dns.hosts` record. The exact allow entry in step 2
  is what lets the local record answer.
- Root ADB on port 5555 has no key check and is open to the whole LAN until reboot. Finish
  the backup and step 9 in the same session.
- Do not disable AiMOR while T3c is your only way in.

## 3. Newer WebView and the kiosk app

Repo docs: `docs/allwinner-a33-pf1007l.md` sections 4 to 7 and `dashboard/kiosk/README.md`.

1. Check free space on `/system` (about 300,000 KiB needed) and that `wm density` is 160.
2. Download Rootless Launcher 3.9.1 (F-Droid) and WebView 106.0.5249.126 ARM (LineageOS
   prebuilt). Check both against the hash table in the repo doc.
3. Add the CA roots GTS R1, GTS R4 (pki.goog) and ISRG Root X1 (letsencrypt.org) to
   `/system/etc/security/cacerts/`. Check each DER SHA-256 against the repo doc.
4. Back up `/system/app/webview` twice, swap in the new WebView, and power-cycle.
   Pass: `dumpsys package com.android.webview` shows versionName 106.0.5249.126.
5. Build the kiosk APK in WSL with JDK 17 (d8 from build-tools 34 fails on JDK 21) and
   `ANDROID_HOME=/opt/android/sdk bash dashboard/kiosk/build.sh`. Install it with `adb -d install`.
6. Point the kiosk at your server:
   `adb -d shell am start -n com.wesbos.homehq/.MainActivity --es url http://<server-ip>:8098/`
7. Make it the start screen. Android 6 shows a "select home app" box. Tap Home HQ, then Always.

## 4. Lock it down

Disable `com.efercro.os.aimor`, `com.yhk.qeota` and `com.DeviceTest` only after you confirm
by hand that the kiosk can still reach Android Settings. `/system/xbin/su` gives root with no
prompt, so install nothing else on a frame that children use.

## Hardware notes for the PF1007L

- It has no battery. Unplugging it powers it off, and the kiosk opens the dashboard again on boot.
- The USB-C port has no CC pull-down resistors, so a USB-C to USB-C charger does not switch it on.
  Use a USB-A to USB-C cable.
- Audio comes only from the built-in speaker. There is no headphone jack, no USB audio and no
  Bluetooth radio, even though Android shows a Bluetooth switch. Set the speaker to maximum with
  `adb shell service call audio 3 i32 3 i32 8 i32 0 s16 com.android.shell`.
