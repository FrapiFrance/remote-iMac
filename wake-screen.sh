#!/bin/bash
# Réveil de l'écran quand la webcam détecte un mouvement.
# Appelé par motion, dans /etc/motion/motion.conf :
#   on_event_start /home/<user>/remote-iMac/wake-screen.sh
#
# Fonctionne sous X11 et sous Wayland (KDE Plasma 6).

if [ -n "$WAYLAND_DISPLAY" ]; then
  kscreen-doctor --dpms on
  # signale une activité : relance le compteur d'inactivité de KDE,
  # pour que l'écran se rééteigne bien après le délai prévu
  busctl --user call org.freedesktop.ScreenSaver /ScreenSaver \
    org.freedesktop.ScreenSaver SimulateUserActivity
else
  export DISPLAY="${DISPLAY:-:0}"
  # un micro-mouvement de souris réveille l'écran
  xdotool mousemove_relative 1 1
fi
