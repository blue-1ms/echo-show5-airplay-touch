# echo-show5-airplay-touch

An optional touchscreen frontend for an **existing** Shairport Sync receiver.
One device is enough. Playback, pause, track navigation, original album artwork,
progress and volume work without pairing. The Android launcher opens the UI in
full screen and provides a dimmed display mode.

The current Android build is named **Echo AirPlay**. It was tested on Echo Show 5
Gen 2 running rooted LineageOS 18.1, with an Alpine chroot and Shairport Sync
5.6.2. Other Android devices, distributions and receiver versions are not yet
validated. The APK alone does **not** install Shairport, root a device, or set up
an audio driver. The existing terminal UI is independent of this companion.


**One Echo is enough. Multiple devices are optional.**

## Compatibility

| Environment | Status |
| --- | --- |
| Echo Show 5, 2nd generation; rooted LineageOS 18.1; Alpine chroot; Shairport Sync 5.6.2 | Tested on two devices |
| A single receiver in the tested environment | Supported by design; unpaired backend and UI checks pass |
| Other Echo Show generations or Echo models | Not tested; do not assume compatible firmware or audio drivers |
| Stock Amazon firmware | No installation path provided by this project |
| Other Android/Linux devices with the required interfaces | Potentially reusable frontend; not hardware-validated |

See [CONFIGURATION.md](CONFIGURATION.md) for the single-device setup and optional
pairing. No ROM, unlock tools, root package, receiver binary or ready-to-flash
image is distributed here. The current UI is in Simplified Chinese; this README
and configuration guide are in English. English UI localization is not yet
implemented.
## Single-device setup (default)

Prerequisites: Python 3.12, dbus-python, and Shairport Sync with metadata, D-Bus
and MPRIS enabled. The Python process must be able to access the receiver's
system D-Bus. The Android app needs only network permission for loopback; it
does not request root.

1. Copy `server.py` and `index.html` into `/opt/echo-touch/` inside the environment
   where Shairport's system D-Bus is available.
2. Configure Shairport's cover-art cache as `/run/echo-airplay/coverart`, or set
   `SHAIRPORT_TOUCH_ART_DIR` to the actual cover directory when starting Python.
3. Run `python3 /opt/echo-touch/server.py`.
4. Open `http://127.0.0.1:8765/` on the same device, or install/open the Android
   APK. The app's info menu can add a launcher shortcut to the home screen.

**Do not create `pair.json` for single-device use.** The default service listens
only on loopback. The info view hides pairing controls and two-device guidance.
Audio routing is left to the existing receiver configuration: this UI does not
split, pan or assign left/right channels.

`start-touch.sh` is an optional idempotent launcher for the tested chroot. Call
it from your existing startup system after D-Bus and Shairport are ready. It is
not a generic Android installer or a systemd unit. Boot behavior of the complete
modified Echo setup has not yet been validated by a full reboot.

## Optional two-device volume linking

This is opt-in and supports **one paired peer**, not an arbitrary speaker group.
Each device must already be a working AirPlay receiver on the same trusted LAN.
Avahi with its D-Bus API is required for discovering the peer. The frontend is
still loopback-only; pairing adds a narrow authenticated peer API on TCP 8766.
Do not forward this port to the Internet. Requests are HMAC-authenticated and
replay-protected, but the small status/volume payloads are not encrypted.

On each device, copy `pair.example.json` to `/opt/echo-touch/pair.json`, then:

- Set `secret` to the **same randomly generated 32-byte hexadecimal key** on both
  devices. Keep it private and give each file mode `0600`.
- Use distinct `self_service` names. Each `peer_service` must exactly match the
  other device's `self_service`. Discovery uses these service identifiers rather
  than assuming stable IP addresses or hostnames.
- Set `peer_name` to a useful display name.
- Keep `linked: false` initially. Restart only the companion Python service,
  then enable volume linking in the info menu after both devices are reachable.

When enabled, a volume change **from either touch UI** sends the same volume
percentage to both receivers. Enabling linking first aligns them to the quieter
receiver. A missing peer produces a visible warning rather than pretending both
were changed. Disabling while the peer is offline disables only this device and
asks you to disable it on the peer too.

This is not an AirPlay group manager. Select both receivers on the sender to
play on both. Changes made independently on the sender are not continuously
mirrored by this feature. Equal percentages also do not guarantee equal acoustic
loudness on different hardware or with different Android media-volume settings.
No fixed left/right placement or stereo separation is assumed.

## Android build

Use JDK 17, platform SDK 30 and Android build tools 30.0.3. The checked-in
`build-local.ps1` expects a toolchain directory containing:

```text
jdk/<jdk-directory>/bin/
platform/android-11/android.jar
tools/android-11/aapt.exe
tools/android-11/lib/d8.jar
tools/android-11/lib/apksigner.jar
```

Run `./build-local.ps1 -ToolchainDirectory <directory>` on Windows. It generates
resources with aapt, Java 8 bytecode with javac, DEX with D8, aligns and signs the
APK. The script generates a **local development signing key** with the standard
development password, outside the source tree. Preserve your own key for
in-place updates; use your own protected release signing setup for distribution.
Do not commit signing keys, device configs, shared pairing keys or live logs.

## Validation and limits

Run `python3 /opt/echo-touch/test_touch.py` with the local service running. Tests
cover artwork confinement, unique HTML IDs, live metadata/artwork, control
authentication, invalid-volume rejection and, when paired, signature/replay
checks. Tests do not intentionally change playback or volume. `node test-ui.js`
checks the single-device and paired UI states without a device.

Real Echo checks covered touch pause/resume, next track, receiver volume,
original artwork, long multilingual metadata, progress, dim/return and launching
from the home-screen shortcut. Linked volume was also confirmed on both devices.
Transport buttons follow MPRIS capability flags. Some senders do not provide all
controls, artwork or progress. Control of tracks acts on the sender's queue;
ordinary unlinked volume controls only the current receiver.

This frontend does not turn an AAC stream into lossless audio, apply EQ or claim
to improve speaker fidelity. The tested Echo audio backend is PulseAudio/AAudio;
direct ALSA on that vendor kernel previously caused crashes and is not part of
these installation instructions.
