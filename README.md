# X96 Remote

Télécommande web (PWA) pour box Android X96 Max, avec liste de chaînes iptv-org.

iPhone (Safari) -> relais `server.py` sur la box (Termux) -> ADB -> la box elle-même.

## 1. Sur la box
1. Paramètres > À propos : 7 appuis sur « Numéro de build ».
2. Options pour les développeurs : activer « Débogage USB » (et « ADB sur réseau » si présent).
3. Installer **Termux** depuis F-Droid (pas le Play Store), puis dans Termux :
   ```sh
   pkg update && pkg install -y python android-tools git
   git clone <url-de-ce-depot> x96-remote && cd x96-remote
   adb connect localhost:5555      # accepter la fenêtre « Autoriser le débogage » (cocher « toujours »)
   python3 server.py
   ```
   Si `localhost:5555` refuse, brancher la box en USB à un PC une fois : `adb tcpip 5555`.
4. Lecteur vidéo conseillé : **VLC** (`org.videolan.vlc`), à indiquer dans l'onglet Chaînes.

## 2. Sur l'iPhone
Safari > `http://IP-DE-LA-BOX:8080` > Partager > « Sur l'écran d'accueil ».
Même Wi-Fi que la box obligatoire.

## Variables
`ADB_TARGET` (défaut `localhost:5555`), `PORT` (défaut `8080`), `ADB`.

## Test sans box
`ADB=tests/fakeadb.sh PORT=8099 python3 server.py`
