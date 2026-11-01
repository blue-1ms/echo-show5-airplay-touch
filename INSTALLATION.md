# Windows installer

## Scope

`Install.cmd` runs `Install.ps1` with a process-local PowerShell execution-policy
override. It does not change the machine-wide execution policy. Review the
scripts before running them. Use the complete extracted repository, including
`dist/` and `installer/`, rather than downloading one script alone.

Supported target: Echo Show 5 Gen 2, `cronos`, Android SDK 30, ARMv7. The target
must already have LineageOS, Magisk and authorized USB debugging. Use one device
at a time, or pass `-Serial`. The installer checks hardware before modifying it.

## What is installed

| Component | Source / behavior |
| --- | --- |
| ADB, if missing | Google's official Windows platform-tools download over HTTPS |
| Termux, if missing | Official v0.118.3 ARMv7 GitHub APK; SHA-256 checked |
| Alpine chroot | Official 3.22.7 ARMv7 minirootfs; SHA-256 checked |
| Python, dbus-python, D-Bus, Avahi and libraries | Signed Alpine v3.22 package repositories |
| Build dependencies | Alpine compiler/autotools, FFmpeg, crypto, plist, PulseAudio and other development packages |
| Shairport Sync 5.6.2 / NQPTP 1.2.9 | Upstream source archives with pinned SHA-256; compiled on the device |
| PulseAudio / AAudio | Signed Termux packages; AAudio sink, no idle-suspend module |
| Touch app / backend | Included APK with checksum and the source files in this repository |
| Startup | Existing-style chroot starter and Magisk service.d hook |

Pinned source/APK hashes are in `installer/downloads.json`. Package repositories
resolve their dependencies automatically and may publish newer patch builds;
this is not a fully reproducible or offline binary bundle. Windows platform-tools
tracks Google's latest download. Upstream components are downloaded from their
maintainers and retain their own licenses; see ATTRIBUTION.md.

## Existing installations

An existing supported receiver is updated in place using the companion upgrade
script. Its `pair.json`, device name and audio configuration are preserved.
The installer backs up companion program files and the boot hook. It does not
rebuild an existing receiver or automatically rewrite its audio configuration.
For the known AAudio idle-suspension workaround, see CONFIGURATION.md.

Fresh installs use `/data/local/echo-airplay`, a generated receiver identity,
loopback-only UI, and no pairing configuration. If a fresh build is interrupted,
its marker allows rerunning the installer. Unknown pre-existing directories are
rejected. A failed build retains files/log output for diagnosis; it does not
flash, factory-reset or delete the device's existing data.

The build keeps source and compiler packages in the chroot for diagnostics.
Future binary distributions must provide the applicable upstream licenses and
corresponding source; the included APK contains only this companion app.

## Troubleshooting

- **No authorized device:** enable USB debugging, accept the computer's key and
  use a data-capable cable. Install the appropriate Windows USB driver if needed.
- **Root denied:** allow Termux in Magisk, then rerun. Do not disable SELinux.
- **Termux first run:** allow its initial bootstrap to finish on the Echo.
- **Signature mismatch:** an existing app was signed with another key; no app
  is automatically removed. Keep a compatible signing key for upgrades.
- **Download checksum mismatch:** stop and use a reviewed updated manifest;
  do not bypass verification.
- **Network failure:** both devices need Internet access for a fresh build. The
  new chroot uses public DNS resolvers; networks blocking them need a local DNS
  configuration before rerunning the build.

## Validation

The Windows prerequisite check and complete in-place upgrade have been executed
on the maintainer's Echo 2. The fresh-runtime dependency/source-build path is
validated separately in a pristine Alpine 3.22.7 chroot: package installation,
NQPTP 1.2.9 build/install, and Shairport Sync 5.6.2 build/install all completed.
The resulting binary reports AirPlay2, PulseAudio, metadata, D-Bus and MPRIS
support. This test did not replace the live audio receiver. A complete clean-device run (including first-run Termux and Magisk
prompts) still needs independent validation. Treat fresh installation as
experimental, not as a promise of unattended setup on an untested device.

Run `python test_installer.py` on Windows for mocked-ADB guard tests (wrong
model, multiple devices, unknown runtime and a read-only supported check).


### Touchscreen feature dependencies

The installer includes the version 1.3 Android launcher and installs the new
Python companion modules on fresh installs and upgrades. Touch pairing uses
Alpine `openssl` (X25519) and `avahi-tools` (discovery); the installer supplies
both. Local output control uses the existing `libpulse` library and AAudio sink,
without requiring the `pactl` command. Backup selection uses Android's system
document picker and does not request broad storage access.


Feature validation on two Echo Show 5 Gen 2 devices (2026-11-01): touchscreen
pairing completed with matching comparison codes; single-device and paired
one-minute sleep tests audibly faded output and paused the iPhone. Both timers
were then cancelled to restore output. Android backup export and import preview
were exercised on Echo 2; backend preference restoration and rejection of
foreign-device pairing backups passed on both devices. The feature suite passed
all 10 tests on Echo 2, including actual OpenSSL X25519 exchanges. Desktop tests
cover clock wake/playback behavior, solo controls and malformed backup previews.
A clock schedule crossing midnight and power-loss recovery have not received
long-duration device testing.

## Optional Home Assistant in version 1.3

The same `Install.cmd` installs both the music touchscreen and the optional
Home panel. There is no separate Home Assistant edition or additional Android
package to install. **Home Assistant is not required for installation or music.**
The app starts on Music and does not load a Home page until you configure one.
Leave Setup untouched for a music-only device; one Echo is sufficient.

For home controls, provide your own reachable Home Assistant server, then use
Setup and sign in on the Echo. The installer does not provision a Home Assistant
server, import your entities, change router rules, or expose any ports.
See [configuration](CONFIGURATION.md#optional-home-assistant-panel).

Version 1.3 was installed on both tested Echo Show 5 Gen 2 devices. The owner
confirmed grouped light control, brightness adjustment and audible music while
switching Music/Home on each. Lights, outlets and Celsius/humidity pages rendered;
login persisted after closing and reopening the app. Outlet power was not toggled
during validation. Existing music UI regression tests remain applicable.
