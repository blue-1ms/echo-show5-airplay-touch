# Configuration

## Start with one receiver

No pairing configuration is required. Leave `pair.json` absent and run:

```sh
python3 /opt/echo-touch/server.py
```

The dashboard listens on `127.0.0.1:8765`. Playback, metadata, artwork and volume
work with one configured Shairport Sync receiver. There is no peer listener and
no two-device onboarding prompt in this mode.

The app does not install or configure the receiver. Shairport Sync must expose
its native D-Bus and MPRIS interfaces on the same system bus. In the existing
Shairport configuration, merge these options into the appropriate sections;
retain the audio backend settings that already work on your device:

```conf
general = {
    name = "Living Room";
    dbus_service_bus = "system";
    mpris_service_bus = "system";
};
metadata = {
    enabled = "yes";
    include_cover_art = "yes";
    cover_art_cache_directory = "/run/echo-airplay/coverart";
};
```

This is a fragment, not a complete replacement configuration. Ensure the cache
directory exists and the receiver can write to it. If your cache path differs,
set the companion's environment to match:

```sh
SHAIRPORT_TOUCH_ART_DIR=/path/to/coverart python3 /opt/echo-touch/server.py
```

The backend only serves supported image files beneath that directory. No
left/right channel routing or stereo-pair configuration is applied.

## Optional pairing

Pair only two already-working receivers. Both must be on the same trusted LAN,
with Avahi's system D-Bus service running. Multicast DNS and TCP 8766 must reach
the peer. Do not expose this port to the Internet.

1. Copy `pair.example.json` to `pair.json` beside `server.py` on each receiver.
2. Generate one shared random key on a trusted device, saving it locally rather
   than printing it into a log:

   ```sh
   python3 -c 'import os,secrets; fd=os.open("pair.key",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,secrets.token_hex(32).encode()); os.close(fd)'
   ```

3. Set `secret` in both private configuration files to that key's contents.
4. Choose two distinct `self_service` names. Point each `peer_service` at the
   other name, exactly. Set `peer_name` to the label shown in the UI.
5. Keep `linked` false initially and set `chmod 600 pair.json` on both devices.
6. Restart the companion on each device. Enable volume linking from the info
   menu once both devices are reachable.

| Field | Meaning |
| --- | --- |
| `secret` | Shared random key; an empty value disables pairing |
| `self_service` | Unique Avahi service name for this companion |
| `peer_service` | The other companion's exact service name |
| `peer_name` | Friendly peer label displayed on this device |
| `linked` | Whether screen volume actions are sent to the paired receiver |

Enabling linking aligns to the lower of the two current volume percentages.
Subsequent volume actions from either touchscreen adjust both receivers. A
missing peer produces a warning; it does not prevent single-device playback.
If you disable linking while the peer is offline, also disable it on that peer
when it returns. To remove pairing completely, stop the companion, remove its
private `pair.json`, and start it again.

Pairing does not select AirPlay destinations, start music on another device, or
mirror every sender-side volume change. Select one or both receivers on the
iPhone/iPad as needed. Equal percentages are not a calibrated loudness match.

## Startup and display

`start-touch.sh` is a small launcher for the tested Alpine chroot layout. Invoke
it from the existing receiver startup chain after D-Bus is available. It is not
a universal boot installer. The full Echo boot sequence remains unverified.

The Android app loads the local dashboard, keeps the screen awake while open,
and optionally dims its own window. The moon control does not adjust the other
receiver or change system brightness settings. The home shortcut opens the
app; it does not install or repair the backend.

## Private files

Do not publish `pair.json`, `pair.key`, signing keystores, device backups, live
logs or personal screenshots. These are not required for other users to run the
project. The checked-in example deliberately contains no usable key.

## Display and recovery

The info menu includes **Auto dim: 3 min / Off**. Each device stores its own
preference. Playback wakes auto-dimmed screens; manually dimmed screens require
a tap. See the README install/upgrade section for prerequisite checks, backups
and the optional boot hook for the tested rooted Echo environment.

### Tested AAudio backend: avoid idle suspension

Reboot/playback validation exposed a hang in the tested native PulseAudio AAudio
backend when `module-suspend-on-idle` closed the stream after five idle seconds.
The process remained alive but subsequent AirPlay streams timed out. On this
specific setup, remove the `load-module module-suspend-on-idle timeout=5` line
from the existing Termux PulseAudio configuration and restart that audio backend
once. Keep `module-aaudio-sink` and the existing local socket configuration.
Do not apply this as a blanket recommendation for other audio drivers.

Display auto dim is independent of audio suspension and remains available.
Keeping the AAudio sink open may use more idle power. The generic frontend
installer deliberately does not edit another project's audio configuration.

The tested chroot keeps `/run` on disk. A stale Avahi PID file can refer to an
unrelated Android process after reboot, causing Avahi's PID-based check to skip
startup. The Echo boot hook removes that stale PID file only when no actual
`avahi-daemon` process is running, before invoking the existing starter.

## Rename a receiver

Open **Help and settings (•••) → AirPlay name**, enter a name such as `Living Room`, then tap **Save name**. Saving restarts this receiver and interrupts its playback; select the new name again in your iPhone or iPad AirPlay picker. The name persists across restarts. Each device can be renamed independently, including a single unpaired receiver. Use distinct names (up to 50 UTF-8 bytes; no control characters or `%` substitutions). The Android device name and home-screen app label are unchanged.

Volume pairing uses stable internal identifiers, so renaming does not require pairing again. Updated peers display the new name after their next successful status refresh.

### Receiver lifecycle and rename recovery

Keep `receiver.py` beside `server.py`. The supplied startup script calls this helper instead of relying on `pgrep` command-name matching. It uses `/run/echo-airplay/receiver.lock` for both watchdog startup and the entire rename/rollback operation. Do not add another independent Shairport launcher. A receiver that does not stop within five seconds is reported as an error; the helper does not start a competing process or force-kill it.

A successful rename preserves pairing configuration and requests the previous receiver volume after restart. The AirPlay sender may set its own volume when reconnecting. If a restart fails, the previous configuration is restored and recovery is attempted. Reconnect from the AirPlay picker after a rename; service readiness alone does not confirm audible playback.


### Peer recovery and playback evidence

Update both paired receivers together. Protocol 2 retains authenticated legacy state requests, but reliable linked controls require protocol 2 on both ends. Controls include a session identifier, increasing sequence number and five-second validity window. Duplicates and older requests are not applied twice; controls are never automatically queued for a disconnected receiver. Response signatures are checked for protocol 2 peers.

A failed probe shows `Reconnecting`. `Offline` requires at least three consecutive failures and more than 15 seconds since the last success. Receiver readiness is separate from connectivity: a reachable companion can report that Shairport is still restarting. Successful addresses are reused; discovery failure does not discard a working cached address. New addresses become cached only after a successful probe.

The backend samples receiver state independently of HTTP requests. Sender playback-rate metadata, explicit stream pause/resume events and MPRIS state feed a shared display state. A rate of zero reports pause even if MPRIS is stale. A flush, quiet music or missing progress alone does not mean pause. Ambiguous active sessions show `Receiving audio`; unknown playback does not trigger automatic dimming. The companion consumes the existing `/tmp/shairport-sync-metadata` FIFO: do not run another consumer of that FIFO at the same time.

Internal diagnostics are bounded to four 256 KiB files under `/run/echo-airplay/diagnostics.log`. They record playback evidence, raw AirPlay volume, displayed volume, link actions and error categories, without pairing keys or authentication tokens. The optional Android-root `installer/observe-audio.sh` records PulseAudio and Android gain for up to one hour, using at most two approximately 512 KiB files in `/data/local/tmp/echo-audio-observation.log`. It does not change volume or start at boot. Diagnostic files are private and are not part of the repository.


## Touchscreen preferences

The Android launcher version 1.2 adds system file selection for backups. Keep
`preferences.py`, `local_audio.py` and `pairing.py` beside `server.py`; use the
complete installer when upgrading. Settings are private files in the companion
directory, not repository configuration.

- **Sleep timer:** 1–180 minutes; the final minute fades local output. At expiry
  the initiating receiver requests iPhone pause. With both devices selected,
  the peer fades to the same deadline without sending a second pause. A peer
  failure is reported and the local timer continues. Expired timers stay muted
  across restarts until **Cancel / restore sound**. Cancellation never resumes
  the sender. A failed pause is reported while local output remains muted.
- **Standby clock:** appears after 60 seconds without interaction while idle or
  paused. Playback or a touch dismisses it. Night hours use Android's local
  time; equal start/end hours disable scheduled dimming. Default hours: 22–07.
- **Layout:** artwork or large text. Swipe long title/artist/album text sideways.
- **Local output limit:** a 0–100% PulseAudio sink gain ceiling, independent of
  the iPhone volume slider and peer linking. This is not a calibrated loudness
  or hearing-protection limit. Default 100%; no compression or normalization.
- **Pairing:** remove an existing pairing before creating another. Open the
  two-minute pairing window on both screens, scan on one, and select the other.
  Compare all 12 hexadecimal characters on both displays, then confirm on each.
  A mismatch must not be approved. X25519 derives a fresh shared key; neither
  discovery alone nor a single confirmation completes pairing. Volume linking
  starts disabled after a new pairing. Removing an offline peer requires
  removing the pairing on that peer separately.
- **Backup:** Save backup opens Android's document picker. Choose backup shows
  a preview before restoration. By default backups contain only the name and
  display/output preferences, not pairing keys or timers. Optional pairing
  data is a secret: store the JSON privately and never upload it to GitHub.
  Pairing restoration is restricted to the original device identity. Restoring
  a name restarts the receiver, so reconnect AirPlay afterward.

Before rolling back to an older backend, cancel sleep timers and restore the
local output limit to 100%; older versions do not manage this sink gain.
