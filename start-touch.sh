#!/bin/sh
set -eu
PIDFILE=/run/echo-airplay/echo-touch.pid
if [ -f "$PIDFILE" ]; then
 pid=$(cat "$PIDFILE")
 if [ -r "/proc/$pid/cmdline" ] && tr '\000' ' ' < "/proc/$pid/cmdline" | grep -q '/opt/echo-touch/server.py'; then exit 0; fi
fi
mkdir -p /run/echo-airplay
nohup /usr/bin/python3 /opt/echo-touch/server.py > /run/echo-airplay/echo-touch.log 2>&1 < /dev/null &
echo $! > "$PIDFILE"
