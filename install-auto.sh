#!/data/data/com.termux/files/usr/bin/sh
# Installe le démarrage automatique du relais X96 Remote.
# 1. Termux:Boot : lance le relais à chaque démarrage de la box.
# 2. Plan B : le relais se lance aussi quand on ouvre Termux.
# Utilisation, une seule fois :  sh ~/x96-remote/install-auto.sh
D="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$HOME/.termux/boot"
cp "$D/termux-boot/x96-remote.sh" "$HOME/.termux/boot/x96-remote.sh"
chmod +x "$HOME/.termux/boot/x96-remote.sh"

if ! grep -q "x96-remote-auto" "$HOME/.bashrc" 2>/dev/null; then
  cat >> "$HOME/.bashrc" <<EOF

# x96-remote-auto : lance le relais à l'ouverture de Termux (sans effet s'il tourne déjà)
cd "$D" && python3 server.py
EOF
fi

echo
echo "C'est installé."
echo "Reste à faire une seule fois : ouvrir l'appli Termux:Boot (F-Droid) pour l'activer."
echo "Ensuite, à chaque démarrage de la box, la télécommande se lance toute seule."
