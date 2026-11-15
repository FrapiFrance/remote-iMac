# remote-iMac

une télécommande pour YouTubeMusicDesktop et MagicMirror sur l'iMac

 <img src="screenshot.jpg" style="zoom:33%;" />
<!-- ![Screenshot](screenshot.jpg) -->

Si vous n'utilisez que YTMDesktop (cas le plus fréquent sans doute :-)) :

- essayez MagicMirror, c'est sympa
- mettez hidePhotos : true dans run/config.json

## musique

Pour les playlists, la file de lecture, repeat et shuffle, on utilise l'API Companion Server de YTMDesktop (testé avec la 2.1.0), voir la [doc](https://ytmdesktop.github.io/developer/companion-server/).

Pour obtenir le token (écrit dans `run/config.json`) :

1. YTMDesktop > Paramètres > Intégrations : activer « Companion server » et « Enable companion authorization »
2. lancer `./ytmd_auth.py`, puis valider le code (bouton Allow) dans la fenêtre qui s'ouvre sur l'écran
3. désactiver « Enable companion authorization » (en 2.1.0, le laisser activé 5 minutes fait planter YTMD)

Si l'API répond `UNAUTHORIZED` et que la fenêtre Paramètres de YTMD reste vide, ses tokens chiffrés sont illisibles ([#1524](https://github.com/ytmdesktop/ytmdesktop/issues/1524)) : YTMD fermé, mettre `integrations.companionServerAuthTokens` à `null` dans `~/.config/YouTube Music Desktop App/config.json`, puis refaire l'appairage.

## photos
Il faut avoir MagicMirror avec [MMM-BackgroundSlideshow](https://github.com/darickc/MMM-BackgroundSlideshow)  et [MMM-Keypress](https://github.com/ItsMeBrille/MMM-Keypress)

Ça affiche en diaporama les photos d'un répertoire de votre disque. Par exemple, que vous auriez récupéré d'un TakeOut GooglePhotos... Avec Keypress, l'affichage est commandé par les flèches, et la télécommande simule les flèches avec xdotool.
Je l'utilise en mode server only docker, avec un firefox en client (et ça marche  même avec plusieurs clients en même temps, local et distants !)

## prérequis

L'ordi concerné est sous kubuntu 24.04 (**X11** nécessaire, pas Wayland)

Il y a un certain nombre de packages nécessaires :

- xdotool,
- playerctl,
- pactl
- je crois que c'est tout

et le fichier [run_at_start.sh](run_at_start.sh) donne un bon exemple de comment lancer les bons programmes (firefox et YouTubeMusicDesktop)

ça pourrait servir à commander plein d'autres trucs (via xdotool et p*ctl, voire d'autres commandes, c'est open)

### TODO

- passer remote en service user ?
- passer à l'API temps réel socket.io de YTMD (plus de rate limit sur /state)
- thumbnail éventuellement, mais bon bof