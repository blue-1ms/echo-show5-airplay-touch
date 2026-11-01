#!/bin/sh
# Run INSIDE an existing receiver environment as root. Never creates pair.json.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEST=/opt/echo-touch
check() {
 command -v python3 >/dev/null
 python3 -c 'import dbus; import sys; assert sys.version_info >= (3, 9)'
 python3 -c 'import dbus; b=dbus.SystemBus(); assert b.name_has_owner("org.mpris.MediaPlayer2.ShairportSync"), "Shairport MPRIS unavailable"'
 [ -r "$SRC/server.py" ] && [ -r "$SRC/index.html" ] && [ -r "$SRC/receiver.py" ] && [ -r "$SRC/installer/start-receiver.sh" ]
 echo "PASS: Python, D-Bus, Shairport MPRIS and source files"
}
check
[ "${1:-}" != "--check" ] || exit 0
[ "$(id -u)" = 0 ] || { echo "Run as root inside the receiver environment"; exit 1; }
mkdir -p "$DEST" /root
python3 -m py_compile "$SRC/server.py"
# Backups contain program files only. Existing private configuration is untouched.
BACKUP="$DEST/backups/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$BACKUP"
for file in receiver.py server.py index.html; do
 [ ! -f "$DEST/$file" ] || cp "$DEST/$file" "$BACKUP/$file"
 cp "$SRC/$file" "$DEST/$file.new"
 chmod 644 "$DEST/$file.new"
 mv "$DEST/$file.new" "$DEST/$file"
done
[ ! -f /root/start-touch.sh ] || cp /root/start-touch.sh "$BACKUP/start-touch.sh"
cp "$SRC/start-touch.sh" /root/start-touch.sh
chmod 755 /root/start-touch.sh
[ ! -f /root/start-receiver.sh ] || cp /root/start-receiver.sh "$BACKUP/start-receiver.sh"
cp "$SRC/installer/start-receiver.sh" /root/start-receiver.sh.new
chmod 755 /root/start-receiver.sh.new
mv /root/start-receiver.sh.new /root/start-receiver.sh
PIDFILE=/run/echo-airplay/echo-touch.pid
if [ -f "$PIDFILE" ]; then
 pid=$(cat "$PIDFILE")
 if [ -r "/proc/$pid/cmdline" ] && tr '\000' ' ' < "/proc/$pid/cmdline" | grep -q '/opt/echo-touch/server.py'; then
  kill "$pid"
  tries=0
  while kill -0 "$pid" 2>/dev/null && [ "$tries" -lt 20 ]; do sleep 1; tries=$((tries+1)); done
  if kill -0 "$pid" 2>/dev/null; then echo "Old service has not exited; retry later"; exit 1; fi
 fi
fi
/bin/sh /root/start-touch.sh
sleep 1
python3 -c 'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8765/api/state",timeout=10); assert r.status==200'
echo "Installed. Previous program files: $BACKUP"
echo "Existing pair.json and receiver/audio settings were preserved."
