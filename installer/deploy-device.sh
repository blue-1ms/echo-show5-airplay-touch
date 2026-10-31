#!/system/bin/sh
set -eu
R=/data/local/echo-airplay
S=/data/local/tmp/echo-touch-installer
T=/data/data/com.termux/files
[ "$(getprop ro.product.device)" = cronos ] || { echo 'Only cronos is supported'; exit 1; }
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
mode=${1:-upgrade}
if [ "$mode" = fresh ]; then
 if [ -e "$R" ] && [ ! -f "$R/.touch-installer-incomplete" ]; then
  echo 'Existing runtime found; refusing to overwrite it'; exit 1
 fi
 mkdir -p "$R"
 touch "$R/.touch-installer-incomplete"
 if [ ! -f "$R/etc/alpine-release" ]; then tar -xzf "$S/alpine.tar.gz" -C "$R"; fi
 for d in dev proc sys; do
  mkdir -p "$R/$d"
  if ! grep -qs " $R/$d " /proc/mounts; then mount -o bind "/$d" "$R/$d"; fi
 done
 mkdir -p "$R/tmp/echo-install" "$R/dev/shm"
 chmod 1777 "$R/tmp" "$R/dev/shm"
 printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' > "$R/etc/resolv.conf"
 cp "$S/shairport-5.6.2.tar.gz" "$S/nqptp-1.2.9.tar.gz" "$S/build-receiver.sh" "$R/tmp/echo-install/"
 chroot "$R" /bin/sh /tmp/echo-install/build-receiver.sh
 # Local identity only; never copied from the maintainer's devices.
 suffix=$(cat /proc/sys/kernel/random/uuid | cut -c1-8)
 cat > "$R/etc/shairport-sync.conf" <<EOF
general = {
 name = "Echo AirPlay $suffix";
 output_backend = "pulseaudio";
 mdns_backend = "avahi";
 interpolation = "vernier";
 default_airplay_volume = -18.0;
 dbus_service_bus = "system";
 mpris_service_bus = "system";
};
pulseaudio = {
 server = "unix:/run/echo-pulse/native";
 sink = "AAudio_sink";
 application_name = "Echo AirPlay";
 output_rate = 48000;
 output_format = "S16_LE";
 output_channels = 2;
};
metadata = { enabled = "yes"; include_cover_art = "yes"; cover_art_cache_directory = "/run/echo-airplay/coverart"; };
EOF
 cat > "$R/etc/avahi/avahi-daemon.conf" <<EOF
[server]
host-name=echo-airplay-$suffix
use-ipv4=yes
use-ipv6=no
allow-interfaces=wlan0
enable-dbus=yes
[publish]
publish-hinfo=no
publish-workstation=no
[reflector]
enable-reflector=no
EOF
 # Keep the AAudio stream open: idle suspension hangs on the tested vendor stack.
 [ ! -f "$T/home/echo-pulse.pa" ] || cp "$T/home/echo-pulse.pa" "$T/home/echo-pulse.before-installer.pa"
 cat > "$T/home/echo-pulse.pa" <<EOF
.fail
load-module module-native-protocol-unix socket=/data/local/tmp/echo-pulse/native auth-anonymous=1
load-module module-aaudio-sink
EOF
 uid=$(stat -c %u "$T")
 chown "$uid:$uid" "$T/home/echo-pulse.pa"
 cp "$S/echo-start.sh" /data/local/echo-start.sh
 cp "$S/echo-pulse-start.sh" /data/local/echo-pulse-start.sh
 cp "$S/start-receiver.sh" "$R/root/start-receiver.sh"
 chmod 755 /data/local/echo-start.sh /data/local/echo-pulse-start.sh
elif [ "$mode" = upgrade ]; then
 [ -x "$R/usr/local/bin/shairport-sync" ] && [ -x /data/local/echo-start.sh ] || { echo 'No supported runtime; use fresh install'; exit 1; }
else
 echo 'Invalid mode'; exit 1
fi
mkdir -p "$R/opt/echo-touch" "$R/tmp/echo-install"
cp "$S/server.py" "$S/index.html" "$S/install.sh" "$S/start-touch.sh" "$R/tmp/echo-install/"
if [ "$mode" = fresh ]; then
 cp "$S/server.py" "$S/index.html" "$R/opt/echo-touch/"
 cp "$S/start-touch.sh" "$R/root/start-touch.sh"
fi
/data/local/echo-start.sh
chroot "$R" /bin/sh /tmp/echo-install/install.sh
mkdir -p /data/adb/service.d
if [ -f /data/adb/service.d/echo-airplay.sh ]; then
 cp /data/adb/service.d/echo-airplay.sh "$R/opt/echo-touch/boot.before-upgrade.sh"
fi
cp "$S/echo-boot.sh" /data/adb/service.d/echo-airplay.sh
chmod 755 /data/adb/service.d/echo-airplay.sh
rm -f "$R/.touch-installer-incomplete"
echo 'Runtime ready. Pairing settings were not created or replaced.'
