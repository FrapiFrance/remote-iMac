# remote-iMac

une télécommande pour YouTubeMusicDesktop et MagicMirror sur l'iMac (en local uniquement)

Il faut avoir MagicMirror avec [MMM-BackgroundSlideshow](https://github.com/darickc/MMM-BackgroundSlideshow)  et [MMM-Keypress](https://github.com/ItsMeBrille/MMM-Keypress)

Et bien sûr YTMDesktop

et un certain nombre de packages nécessaires (xdotool, playerctl, pactl ...)

L'ordi concerné est sous kubuntu 24.04 (X11 nécessaire)

![Screenshot](screenshot.jpg){width=50%}

## TODO

- d'abord corriger le problème des photos mal orientées...
- passer remote en service user

- gestion du "off" qui est moche
- listbox playlist, avec bascule via  [changeVideo](https://ytmdesktop.github.io/developer/companion-server/reference/v1/command.html#change-video)
- listbox queue en cours
- gestion du shuffle pas conforme à la spec...
- thumbnail éventuellement, mais bon bof