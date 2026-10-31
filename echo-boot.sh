#!/system/bin/sh
# Optional Magisk service.d hook for the tested Echo environment only.
(
 count=0
 while [ "$(getprop sys.boot_completed)" != "1" ] && [ "$count" -lt 150 ]; do
  sleep 2
  count=$((count+1))
 done
 [ "$(getprop sys.boot_completed)" = "1" ] || exit 1
 [ -x /data/local/echo-start.sh ] || exit 1
 sleep 5
 start_receiver() {
  # A persistent /run PID may now belong to an unrelated Android process.
  if ! pidof avahi-daemon >/dev/null; then
   rm -f /data/local/echo-airplay/run/avahi-daemon/pid
  fi
  /data/local/echo-start.sh
 }
 # The existing starter must be idempotent. It owns the receiver/audio setup.
 start_receiver > /data/local/echo-airplay-start.log 2>&1
 am start -n io.blue1ms.echoairplay/.MainActivity >> /data/local/echo-airplay-start.log 2>&1
 while true; do
  sleep 30
  start_receiver > /data/local/echo-airplay-health.log 2>&1
 done
) &
