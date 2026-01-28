#!/bin/bash
# --- CONFIG ---
URL="http://localhost:8080"
DESKTOP_FIREFOX=0     # Bureau 1 (index commence à 0)
DESKTOP_MUSIC=1       # Bureau 2
rm  ~/error_*.log
# --- VNC ---
~/vnc.sh 2>&1 > ~/error_vnc.log &
# --- YOUTUBE MUSIC ---
youtube-music-desktop-app 2>&1 > ~/error_yt.log &
# attendre que la fenêtre existe vraiment
for i in {1..20}; do
  WIN_ID=$(wmctrl -lx | grep YouTube | sed 's/.*imac142 //')
  [ -n "$WIN_ID" ] && break
  sleep 0.5
done
# fullscreen
wmctrl -i -r "$WIN_ID" -b add,fullscreen 2>&1 >> ~/error_run_at_start.log
sleep 1
# envoyer sur le bon bureau
wmctrl -i -r "$WIN_ID" -t "$DESKTOP_MUSIC" 2>&1 >> ~/error_run_at_start.log
# pour que YTMDesktop réponse bien aux commandes (playerctl ou ytmdesktop_api_call), j'ai dû
# le mettre en lancement auto de la musique au démarrage
# et donc dès que possible, je le mets en pause
sleep 7 # au moins 5, pour que le player soit bien prêt
playerctl -l  2>&1 >> ~/error_run_at_start.log
playerctl pause 2>&1 >> ~/error_run_at_start.log


# --- FIREFOX --- --start-fullscreen est KO, tant pis
# laisser le temps à docker de se charger tranquillement
sleep 20
firefox "$URL" 2>&1 > ~/error_kiosk.log &
# attendre que la fenêtre existe vraiment
for i in {1..20}; do
  WIN_ID=$(wmctrl -lx | grep Firefox | sed 's/.*imac142 //')
  [ -n "$WIN_ID" ] && break
  sleep 0.5
done
# fullscreen
wmctrl -r "$WIN_ID" -b add,fullscreen 2>&1 >> ~/error_run_at_start.log
sleep 1
# envoyer sur le bon bureau
wmctrl -r "$WIN_ID" -t $DESKTOP_FIREFOX 2>&1 >> ~/error_run_at_start.log
# donner le focus
wmctrl -i -R "$WIN_ID" 2>&1 >> ~/error_run_at_start.log

# --- YOUTUBE MUSIC REMOTE ---
~/remote-iMac/ytremote.py 2>&1 > ~/error_ytremote.log &
