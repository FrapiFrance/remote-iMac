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

- deux pages/onglets pour 
  - photos (en récupérant l'url gphotos de la photo affichée - refresh ?) 
  - et musique
Dans musique :
- avec https://ytmdesktop.github.io/developer/companion-server/reference/v1/state.html
- on laisse les commandes "std" avec playerctl, mais
- ajouter dans get_status() 
  - la playlist sélectionnée (/state) dans la liste (/playlists fait au lancement du serveur - quid si ytm était éteint ? un bouton refresh list ?) 
  - la queue et l'index de la chanson en cours (à partir de /state)
  - l'url de thumbnail de 302px de large
- ajouter 2 listbox
  - liste des playlists, dont celle sélectionnée (s'il y en a une)
  - liste des chansons de la queue, dont celle sélectionnée
- ça lance https://ytmdesktop.github.io/developer/companion-server/reference/v1/command.html#change-video
