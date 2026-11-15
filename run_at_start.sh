#!/bin/bash
# Démarrage du PC kiosque : un seul bureau.
#   - YouTube Music Desktop (YTMD) est lancé en premier, il reste derrière
#   - Firefox (affichage photos) est lancé ensuite, en plein écran, au premier plan

# --- CONFIG ---
URL="http://localhost:8080"
LOG=~/error_run_at_start.log
DOCKER_TIMEOUT=120   # s max d'attente du serveur photos
PLAYER_TIMEOUT=60    # s max d'attente du lecteur YTMD
WINDOW_TIMEOUT=30    # s max d'attente d'une fenêtre

rm -f ~/error_*.log

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# wait_window <motif> : attend une fenêtre dont la ligne `wmctrl -lx` contient
# <motif> (insensible à la casse), affiche son id (la première trouvée).
wait_window() {
  local id i
  for ((i = 0; i < WINDOW_TIMEOUT * 2; i++)); do
    id=$(wmctrl -lx | grep -i -- "$1" | head -1 | cut -d' ' -f1)
    [ -n "$id" ] && { echo "$id"; return 0; }
    sleep 0.5
  done
  return 1
}

# --- VNC ---
~/vnc.sh > ~/error_vnc.log 2>&1 &

# --- YOUTUBE MUSIC ---
youtube-music-desktop-app > ~/error_yt.log 2>&1 &
# Firefox n'est pas encore lancé : "youtube" ne peut désigner que YTMD
if WIN_ID=$(wait_window youtube); then
  log "youtube:$WIN_ID"
  wmctrl -i -r "$WIN_ID" -b add,fullscreen >> "$LOG" 2>&1
else
  log "youtube: fenêtre introuvable après ${WINDOW_TIMEOUT}s"
fi

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

# --- FIREFOX --- (--start-fullscreen est KO, d'où wmctrl)
# attendre que le serveur photos (docker) réponde
for ((i = 0; i < DOCKER_TIMEOUT; i++)); do
  curl -sf -o /dev/null "$URL" && break
  sleep 1
done
log "serveur $URL: attendu ${i}s"

firefox "$URL" > ~/error_kiosk.log 2>&1 &
# la classe de la fenêtre Firefox (Navigator.firefox) contient "firefox"
if WIN_ID=$(wait_window firefox); then
  log "firefox:$WIN_ID"
  wmctrl -i -r "$WIN_ID" -b add,fullscreen >> "$LOG" 2>&1
  sleep 1
  # premier plan + focus : Firefox passe devant YTMD
  wmctrl -i -a "$WIN_ID" >> "$LOG" 2>&1
else
  log "firefox: fenêtre introuvable après ${WINDOW_TIMEOUT}s"
fi

# --- YOUTUBE MUSIC REMOTE ---
~/remote-iMac/ytremote.py > ~/error_ytremote.log 2>&1 &

# --- MOTION ---
# inutile, il est en service
