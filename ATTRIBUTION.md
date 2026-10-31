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
Its source and binaries are not included in this repository. The tested audio
setup also uses NQPTP, Avahi, PulseAudio/AAudio, Termux and LineageOS; these remain
separate projects with their own licenses and installation requirements.

Amazon, Echo, Apple, AirPlay and related product names belong to their respective
owners. This is an independent experimental project, not an official Amazon or
Apple product.
