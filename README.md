# remote-iMac

une télécommande pour YouTubeMusicDesktop et MagicMirror sur l'iMac (en local uniquement)

Il faut avoir MagicMirror avec [MMM-BackgroundSlideshow](https://github.com/darickc/MMM-BackgroundSlideshow)  et [MMM-Keypress](https://github.com/ItsMeBrille/MMM-Keypress)

Et bien sûr YTMDesktop

et un certain nombre de packages nécessaires (xdotool, playerctl, pactl ...)

Pour les playlists et la file de lecture, on utilise l'API YTMDesktop, see [doc](https://ytmdesktop.github.io/developer/companion-server/reference/v1/auth-requestcode.html)  to get the token

L'ordi concerné est sous kubuntu 24.04 (X11 nécessaire)

![Screenshot](screenshot.jpg){width=50%}

## TODO

- d'abord corriger le problème des photos mal orientées...
- passer remote en service user

- gestion du shuffle pas conforme à la spec... faut trouver où ds state il me renvoie l'info de shuffled ou pas.
    en shuff, on a tjrs selectedItemIndex à 0; ms ds la 1e chanson de normal, aussi
    en regardant ds le code de https://github.com/ytmdesktop/ytmdesktop , je trouve pas de shuffle en state, juste en action (donc qui comm ande le bouton de l'interface ?) 
- thumbnail éventuellement, mais bon bof