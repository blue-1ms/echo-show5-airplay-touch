#!/bin/sh
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
apk update
apk add ca-certificates openssl dbus avahi avahi-tools python3 py3-dbus libpulse \
 build-base autoconf automake libtool pkgconf avahi-dev libconfig-dev \
 openssl-dev popt-dev soxr-dev pulseaudio-dev glib-dev libsodium-dev \
 libgcrypt-dev libplist-dev libplist-util util-linux-dev ffmpeg-dev xxd
mkdir -p /root/build
cd /root/build
# Always unpack pristine sources: never mix objects from different configure flags.
tar xzf /tmp/echo-install/shairport-5.6.2.tar.gz
tar xzf /tmp/echo-install/nqptp-1.2.9.tar.gz
cd nqptp-1.2.9
autoreconf -fi
./configure --prefix=/usr/local
make -j1
make install
cd ../shairport-sync-5.6.2
autoreconf -fi
./configure --prefix=/usr/local --sysconfdir=/etc --with-pulseaudio \
 --with-soxr --with-avahi --with-ssl=openssl --with-airplay-2 \
 --with-metadata --with-dbus-interface --with-mpris-interface
make -j1
make install
/usr/local/bin/shairport-sync -V
