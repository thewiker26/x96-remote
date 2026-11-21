#!/bin/sh
echo "FAKEADB $@" >> /tmp/fakeadb.log
case "$1" in connect) echo "connected to $2";; -s) case "$3" in get-state) echo device;; shell) [ "$4" = "pm list packages -3" ] && printf 'package:org.videolan.vlc\npackage:org.xbmc.kodi\n';; esac;; esac
exit 0
