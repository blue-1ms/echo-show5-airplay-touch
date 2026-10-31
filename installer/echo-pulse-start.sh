#!/system/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:/system/bin
export TMPDIR=$PREFIX/tmp
if ! pulseaudio --check; then
 pulseaudio -n --daemonize=yes --exit-idle-time=-1 --log-target=file:$HOME/echo-pulse.log -F $HOME/echo-pulse.pa
fi
