#!/bin/sh
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /run/dbus /run/echo-airplay/coverart /dev/shm
chmod 1777 /dev/shm
dbus-uuidgen --ensure
if ! pgrep -x dbus-daemon >/dev/null; then dbus-daemon --system --fork --nopidfile; fi
if ! pgrep -x avahi-daemon >/dev/null; then
 rm -f /run/avahi-daemon/pid
 avahi-daemon --no-drop-root --no-chroot > /run/echo-airplay/avahi-daemon.log 2>&1 &
fi
if ! pgrep -x nqptp >/dev/null; then
 nqptp > /run/echo-airplay/nqptp.log 2>&1 &
fi
sleep 2
/usr/bin/python3 /opt/echo-touch/receiver.py
/bin/sh /root/start-touch.sh
