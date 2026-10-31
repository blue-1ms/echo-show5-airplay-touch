#!/system/bin/sh
set -eu
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:/system/bin
export TMPDIR=$PREFIX/tmp
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y pulseaudio
test -f "$PREFIX/lib/pulseaudio/modules/module-aaudio-sink.so"
