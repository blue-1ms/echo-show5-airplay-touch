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
