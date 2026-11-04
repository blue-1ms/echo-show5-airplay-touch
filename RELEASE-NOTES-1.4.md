# Version 1.4 — Optional touch Library and conditional navigation

- Compact top tabs replace the bottom dock and Pages popup. Only configured services appear; no HA/MA URLs means pure AirPlay.
- Optional Echo-sized Music Assistant Library: songs, favorite tracks, albums, playlists, search, explicit player selection, artwork, transport controls, and volume slider/+/-.
- Group volume adjustments set current members to an equal percentage; serialized latest-input handling and bounded readback prevent stale refreshes during adjustment. No background volume enforcement.
- Full MA remains available. Home Assistant uses its existing optional isolated WebView.
- Consistent AirPlay header icon alignment and full-height content.

Upgrade with Install.cmd from the complete ZIP. The bundled APK is version1.4/code5 and its SHA-256 is checked before installation. Existing app settings and logins are preserved by install -r. No root/ROM changes, home-specific addresses, credentials, EQ, pairing or delay calibration are bundled.

Verified: signed APK build; 41 Python checks (4 skipped); AirPlay UI regression checks; Library null-success/group-volume/single-player checks; actual music-only no-tab state; two-Echo browsing, audible synchronized MA playback and stable equal volume accepted by owner. Some list artwork is unavailable. Full receiver rebuild/fresh-ROM flashing and reboot recovery were not repeated for this release. Other device models and MA versions remain unvalidated.
