#!/bin/bash
# Démarrage du PC kiosque : un seul bureau.
#   - YouTube Music Desktop (YTMD) est lancé en premier, il reste derrière
#   - Firefox (affichage photos) est lancé ensuite, en mode kiosque (plein écran), au premier plan
#
# Aucune manipulation de fenêtre ici (pas de wmctrl), donc ça marche sous X11 comme sous Wayland.
# Pour que YTMD soit lui aussi en plein écran derrière, utiliser une règle de fenêtre KWin
# (voir README).

# --- CONFIG ---
URL="http://localhost:8080"
LOG=~/error_run_at_start.log
DOCKER_TIMEOUT=120   # s max d'attente du serveur photos
PLAYER_TIMEOUT=60    # s max d'attente du lecteur YTMD

rm -f ~/error_*.log

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# --- VNC ---
~/vnc.sh > ~/error_vnc.log 2>&1 &

# --- YOUTUBE MUSIC ---
youtube-music-desktop-app > ~/error_yt.log 2>&1 &

# YTMD n'obéit bien à playerctl que s'il lance la musique tout seul au démarrage,
# donc on attend qu'il joue, puis on le met en pause.
for ((i = 0; i < PLAYER_TIMEOUT; i++)); do
  [ "$(playerctl status 2>/dev/null)" = "Playing" ] && break
  sleep 1
done
log "player: statut '$(playerctl status 2>&1)' après ${i}s"
playerctl -l >> "$LOG" 2>&1
sleep 2   # marge pour que le player soit vraiment prêt
playerctl pause >> "$LOG" 2>&1

# --- FIREFOX ---
# attendre que le serveur photos (docker) réponde
for ((i = 0; i < DOCKER_TIMEOUT; i++)); do
  curl -sf -o /dev/null "$URL" && break
  sleep 1
done
log "serveur $URL: attendu ${i}s"

# --kiosk : plein écran sans interface ; lancé en dernier, Firefox passe devant YTMD
# (Alt+F4 pour en sortir)
firefox --kiosk "$URL" > ~/error_kiosk.log 2>&1 &

# --- YOUTUBE MUSIC REMOTE ---
~/remote-iMac/ytremote.py > ~/error_ytremote.log 2>&1 &

# --- MOTION ---
# inutile, il est en service
