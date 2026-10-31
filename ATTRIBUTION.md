# Attribution

This touchscreen companion grew out of local work alongside
[shairport-sync-tui](https://github.com/blue-1ms/shairport-sync-tui).
The original MIT copyright notice is retained in `LICENSE`.

The tested Echo Show 5 Gen 2 (`cronos`) environment depends on two XDA projects:

- [Unofficial LineageOS 18.1 for the Amazon Echo Show 5 (2021)](https://xdaforums.com/t/rom-unofficial-11-cronos-lineageos-18-1-for-the-amazon-echo-show-5-2021.4772598/):
  credit to the ROM maintainers and contributors, and the LineageOS community.
- [Unlock / Root / TWRP / Unbrick for Echo Show 5, 2nd Gen (2021)](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-show-5-2nd-gen-2021-cronos.4772596/):
  credit to the developers and contributors responsible for the device unlock
  and recovery support.

Their work made this device setup possible. This repository does not claim
authorship of the unlock, recovery or Android port. Refer to those original
threads for their full credits and installation requirements.

The receiver is [Shairport Sync](https://github.com/mikebrady/shairport-sync),
by **Mike Brady and contributors**. It provides AirPlay / AirPlay 2 reception,
playback synchronization, metadata and control interfaces. This companion's
touchscreen controls and optional volume linking build on that work; they do
not implement the underlying AirPlay receiver or audio synchronization engine.
See the upstream [AUTHORS](https://github.com/mikebrady/shairport-sync/blob/master/AUTHORS)
and [LICENSES](https://github.com/mikebrady/shairport-sync/blob/master/LICENSES)
for contributor credits and licensing.
Its source and binaries are not included in this repository.

## Runtime, platform and device setup

Credit and thanks to the authors, maintainers, packagers and contributors of:

| Project | Role in the tested setup |
| --- | --- |
| [NQPTP](https://github.com/mikebrady/nqptp), by Mike Brady and contributors | Monitors timing information used for AirPlay 2 synchronization |
| [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/) | Audio server and Shairport output backend |
| [Termux app](https://github.com/termux/termux-app) and [Termux packages](https://github.com/termux/termux-packages) | Android native execution environment, packages and platform integration |
| [Termux PulseAudio packaging and patches](https://github.com/termux/termux-packages/tree/master/packages/pulseaudio) | Android audio integration, including the AAudio sink used here |
| [Avahi](https://github.com/avahi/avahi) | mDNS/DNS-SD discovery and its D-Bus API |
| [D-Bus](https://www.freedesktop.org/wiki/Software/dbus/) and [dbus-python](https://dbus.freedesktop.org/doc/dbus-python/) | Interprocess messaging and Python bindings |
| [Python / CPython](https://github.com/python/cpython) | Companion HTTP server, state/control logic and tests |
| [Alpine Linux](https://alpinelinux.org/), [musl](https://musl.libc.org/) and [BusyBox](https://busybox.net/) | Chroot distribution, C runtime and shell utilities |
| [Android Open Source Project](https://source.android.com/) | Android framework, AAudio, platform/build tools and device platform foundation |
| [Chromium](https://www.chromium.org/) | WebView rendering engine |
| [LineageOS](https://lineageos.org/) | Upstream OS project underlying the separately credited XDA device port |
| [Magisk](https://github.com/topjohnwu/Magisk), by John Wu and contributors | Root management and boot-service hooks |
| [TWRP / Team Win Recovery Project](https://twrp.me/) | Recovery environment used during device installation; device-specific work is credited in the XDA thread above |

## Receiver libraries

The tested Shairport Sync build links to these projects. They are dependencies
of the receiver environment, rather than bundled implementations in this UI:

- [FFmpeg](https://ffmpeg.org/): codec, audio utility and resampling libraries.
- [OpenSSL](https://www.openssl.org/), [libsodium](https://github.com/jedisct1/libsodium)
  and [Libgcrypt / libgpg-error](https://gnupg.org/software/libgcrypt/): cryptographic libraries and support.
- [libplist](https://github.com/libimobiledevice/libplist): property-list processing.
- [GLib / GObject / GIO](https://gitlab.gnome.org/GNOME/glib): supporting runtime and messaging interfaces.
- [libsoxr](https://sourceforge.net/projects/soxr/): optional high-quality resampling
  support compiled into the receiver. The tested configuration uses Vernier
  interpolation; this credit does not imply that SoXR is the selected mode.
- [libconfig](https://hyperrealm.github.io/libconfig/): receiver configuration parsing.
- [popt](https://github.com/rpm-software-management/popt): command-line option parsing.
- [util-linux](https://github.com/util-linux/util-linux): UUID and supporting system libraries.

Distribution packages also bring transitive dependencies (for example codec,
compression and system-support libraries). Credit belongs to their respective
upstream authors and packagers too. This is a component acknowledgment, not a
complete software bill of materials for an Android ROM or Alpine installation;
consult the installed package metadata and upstream copyright/license files
for the complete dependency and license inventory of a particular build.

## Build and development tools

Thanks also to [OpenJDK](https://openjdk.org/), the Android build tools and
[R8/D8](https://r8.googlesource.com/r8), [Node.js](https://nodejs.org/),
[PowerShell](https://github.com/PowerShell/PowerShell), [Git](https://git-scm.com/),
and the [GNU toolchain](https://www.gnu.org/software/) used to build, test and
maintain the companion and its receiver environment.

All upstream projects retain their own copyright and license terms. This
repository's MIT license does not relicense those projects. Refer to each
linked upstream project for its full contributors and licensing information.

Amazon, Echo, Apple, AirPlay and related product names belong to their respective
owners. This is an independent experimental project, not an official Amazon or
Apple product.
