# X96 Remote

Télécommande web (PWA) pour box Android X96 Max, avec chaînes iptv-org.

iPhone (Safari) -> relais `server.py` sur la box (Termux) -> ADB -> la box elle-même.

## Fonctions
- **Boutons** : flèches, OK, retour, accueil, menu, applis ouvertes, lecture, volume, chiffres, veille (avec confirmation). Appui long = répétition.
- **Chaînes** (iptv-org) : par pays, Foot, Sport, Infos, Enfants, Films, Musique. Favoris, récentes, recherche, zapping suivante/précédente, « Vérifier celles qui marchent » (cache les flux morts).
- **Clavier** : écriture en direct sur la TV (accents retirés), valider, effacer, raccourcis (www., .com, @gmail.com).
- **Souris** : pavé tactile (clic, glisser pour défiler) et boutons de défilement.
- **Applis** : lance Kodi, Netflix, YouTube… ; raccourcis Réglages, Wi-Fi, Affichage, Son, Bluetooth.
- Texte plus grand, thème clair/sombre automatique, aide intégrée, mise à jour en un bouton.
- Code d'accès facultatif : `X96_PIN=1234 python3 server.py`.

## 1. Sur la box
1. Paramètres > À propos : 7 appuis sur « Numéro de build ».
2. Options pour les développeurs : activer « Débogage USB » (et « ADB sur réseau » si présent).
3. Installer **Termux** depuis F-Droid (pas le Play Store), puis dans Termux :
   ```sh
   pkg install -y python android-tools git
   git clone https://github.com/thewiker26/x96-remote
   cd x96-remote && git checkout claude/bold-dijkstra-ylczdk
   adb connect localhost:5555      # accepter « Toujours autoriser »
   python3 server.py
   ```
4. Si `adb` ne démarre pas (erreur « CANNOT LINK EXECUTABLE ») : `pip install adb-shell`, le relais passe seul en mode Python.

## 2. Sur l'iPhone
Safari > `http://IP-DE-LA-BOX:8080` > Partager > « Sur l'écran d'accueil ». Même Wi-Fi que la box.

## Démarrage automatique (à faire une seule fois)
1. Installer **Termux:Boot** depuis F-Droid et l'ouvrir une fois.
2. Dans Termux : `cd x96-remote && git pull && sh install-auto.sh`

Ensuite le relais se lance seul à chaque démarrage de la box, et aussi quand on ouvre Termux (plan B).
Il se reconnecte seul à l'ADB de la box s'il n'est pas prêt au démarrage.

## Mise à jour
Bouton « Vérifier » dans l'onglet Applis (ou `git pull` dans le dossier).

## Variables
`ADB_TARGET` (défaut `localhost:5555`), `PORT` (8080), `ADB`, `ADB_MODE` (bin|py), `X96_PIN`, `IPTV_BASE`.

## Test sans box
`ADB=tests/fakeadb.sh PORT=8099 python3 server.py`
