#!/bin/sh
# Faux adb pour tester sans box : journalise les commandes dans /tmp/fakeadb.log
echo "FAKEADB $@" >> /tmp/fakeadb.log
case "$1" in
  connect) echo "connected to $2";;
  -s) case "$3" in
        get-state) echo device;;
        shell) case "$4" in
                 "pm list packages -3") printf 'package:org.videolan.vlc\npackage:org.xbmc.kodi\npackage:com.netflix.mediaclient\npackage:com.termux\n';;
                 "wm size") echo "Physical size: 1920x1080";;
               esac;;
      esac;;
esac
exit 0
