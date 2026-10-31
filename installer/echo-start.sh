#!/system/bin/sh
set -eu
R=/data/local/echo-airplay
T=/data/data/com.termux/files
[ -x "$R/usr/local/bin/shairport-sync" ] || exit 1
[ -x "$T/usr/bin/pulseaudio" ] || exit 1
for d in dev proc sys; do
 mkdir -p "$R/$d"
 if ! grep -qs " $R/$d " /proc/mounts; then mount -o bind /$d "$R/$d"; fi
done
mkdir -p /data/local/tmp/echo-pulse "$R/run/echo-pulse"
uid=$(stat -c %u "$T")
chown "$uid:$uid" /data/local/tmp/echo-pulse
chmod 700 /data/local/tmp/echo-pulse
if ! grep -qs " $R/run/echo-pulse " /proc/mounts; then
 mount -o bind /data/local/tmp/echo-pulse "$R/run/echo-pulse"
fi
run-as com.termux /system/bin/sh /data/local/echo-pulse-start.sh
chroot "$R" /usr/bin/env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /bin/sh /root/start-receiver.sh
