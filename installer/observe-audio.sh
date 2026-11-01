#!/system/bin/sh
# Optional bounded diagnostic capture; never changes audio settings.
set -eu
umask 077
LOG=/data/local/tmp/echo-audio-observation.log
PIDFILE=/data/local/tmp/echo-audio-observation.pid
if [ -f "$PIDFILE" ]; then
 old=$(cat "$PIDFILE")
 if [ -r "/proc/$old/cmdline" ] && tr '\000' ' ' < "/proc/$old/cmdline" | grep -q '/observe-audio.sh'; then
  echo 'Observation already running'; exit 0
 fi
fi
echo $$ > "$PIDFILE"
T=/data/data/com.termux/files/usr/bin
end=$(( $(date +%s) + 3600 ))
echo "START $(date +%s)" >> "$LOG"
while [ "$(date +%s)" -lt "$end" ]; do
 if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 524288 ]; then mv "$LOG" "$LOG.1"; fi
 {
  echo "SAMPLE $(date +%s)"
  run-as com.termux "$T/timeout" 4 "$T/pactl" -s unix:/data/local/tmp/echo-pulse/native list sinks | sed -n '/State:/p;/Name:/p;/Mute:/p;/Volume:/p;/balance /p'
  run-as com.termux "$T/timeout" 4 "$T/pactl" -s unix:/data/local/tmp/echo-pulse/native list sink-inputs | sed -n '/Sink Input #/p;/Corked:/p;/Mute:/p;/Volume:/p;/application.process.id/p'
  dumpsys audio | sed -n '/- STREAM_MUSIC:/,/Devices:/p'
 } >> "$LOG" 2>&1
 sleep 5
done
echo "END $(date +%s)" >> "$LOG"
