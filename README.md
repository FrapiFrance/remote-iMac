# remote-iMac

une télécommande pour YouTubeMusicDesktop et MagicMirror sur l'iMac

 <img src="screenshot.jpg" style="zoom:33%;" />
<!-- ![Screenshot](screenshot.jpg) -->

Si vous n'utilisez que YTMDesktop (cas le plus fréquent sans doute :-)) :

- essayez MagicMirror, c'est sympa
- mettez hidePhotos : true dans run/config.json

## musique

Pour les playlists et la file de lecture, on utilise l'API YTMDesktop, see [doc](https://ytmdesktop.github.io/developer/companion-server/reference/v1/auth-requestcode.html)  to get the token

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
- gestion du shuffle pas conforme à la spec... faut trouver où ds state il me renvoie l'info de shuffled ou pas.
    en shuff, on a tjrs selectedItemIndex à 0; ms ds la 1e chanson de normal, aussi
    en regardant ds le code de https://github.com/ytmdesktop/ytmdesktop , je trouve pas de shuffle en state, juste en action (donc qui comm ande le bouton de l'interface ?) 
- thumbnail éventuellement, mais bon bof