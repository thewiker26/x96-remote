#!/data/data/com.termux/files/usr/bin/sh
# Lance le relais X96 Remote au démarrage de la box (nécessite Termux:Boot).
termux-wake-lock
sleep 20
cd "$HOME/x96-remote" || exit 1
adb connect localhost:5555
exec python3 server.py >> "$HOME/x96-remote.log" 2>&1
