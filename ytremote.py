#!/usr/bin/env python3
# avec photos : Précédent / Pause / Suivant
from datetime import datetime
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse
import re
import os
import time
from ytm_api_client import ytmdesktop_api_call  # type: ignore

HOST = "0.0.0.0"
PORT = 8000

YTMD_CACHE_DELAY = 30  # secondes (* 60 pour liste des playlists, donc 30 minutes)

# Si tu veux cibler un player précis, décommente et ajuste :
# PLAYER = "youtube-music-desktop-app"
# BASE_CMD = ["playerctl", "-p", PLAYER]
BASE_CMD = ["playerctl"]


MANIFEST: dict[str, str | list[dict[str, str]]] = {
    "name": "remote iMac",
    "short_name": "remote iMac",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#003366",
    "theme_color": "#003366",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
}

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(SCRIPT_DIR, "icon.svg"), "r", encoding="utf-8") as f:
    ICON_SVG = f.read()

with open(os.path.join(SCRIPT_DIR, "js", "sw.js"), "r", encoding="utf-8") as f:
    SW_JS = f.read()

with open(os.path.join(SCRIPT_DIR, "ytremote.html"), "r", encoding="utf-8") as f:
    HTML = f.read()

with open(os.path.join(SCRIPT_DIR, "css", "ytremote.css"), "r", encoding="utf-8") as f:
    CSS = f.read()

with open(os.path.join(SCRIPT_DIR, "js", "ytremote.js"), "r", encoding="utf-8") as f:
    JS = f.read()


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def run_playerctl(args: list[str]):
    try:
        return run_cmd(BASE_CMD + args)
    except Exception as e:
        return 1, str(e)


def run_ytmdesktop_api_call(args: list[str | None]) -> tuple[int, dict | None]:
    ok, data = ytmdesktop_api_call(*args)
    # print(f"{datetime.now()} YTMD call {args} returned ok={ok}")
    return (0 if ok else 1), data


def run_xdotool_key(keysym: str) -> tuple[int, str]:
    # Use a shell so we can "export DISPLAY=:0 && ..."
    cmd = ["bash", "-lc", f"export DISPLAY=:0; xdotool key {keysym}"]
    try:
        return run_cmd(cmd)
    except Exception as e:
        return 1, str(e)


def run_xdotool_key_to_firefox(keysym: str) -> tuple[int, str]:
    # active une fenêtre Firefox puis envoie la touche
    # --onlyvisible évite les fenêtres cachées ; --class firefox marche bien en général
    cmd = [
        "bash",
        "-lc",
        "export DISPLAY=:0; "
        "WID=$(xdotool search --onlyvisible --class firefox | head -n1); "
        'if [ -z "$WID" ]; then exit 2; fi; '
        # pas nécessaire d'activer la fenêtre
        #'xdotool windowactivate --sync "$WID"; '
        f'xdotool key --window "$WID" {keysym}',
    ]
    try:
        return run_cmd(cmd)
    except Exception as e:
        return 1, str(e)


def get_system_volume():
    # Returns (volume_int_0_100, muted_bool)
    rc, out = run_cmd(["bash", "-lc", "pactl get-sink-volume @DEFAULT_SINK@"])
    vol = None
    if rc == 0:
        # Example: "Volume: front-left: 65536 / 100% / 0.00 dB, ..."

        m = re.search(r"(\d+)%", out)
        if m:
            vol = int(m.group(1))

    rc2, out2 = run_cmd(["bash", "-lc", "pactl get-sink-mute @DEFAULT_SINK@"])
    muted = False
    if rc2 == 0:
        muted = "yes" in out2.lower()

    return (vol if vol is not None else 0, muted)


def get_playback_position_and_length():
    # position: seconds (float), length: seconds (int) if known
    rc_pos, out_pos = run_playerctl(["position"])
    pos = 0.0
    if rc_pos == 0:
        try:
            pos = float(out_pos.strip())
        except Exception:
            pos = 0.0

    # mpris:length is microseconds
    rc_len, out_len = run_playerctl(["metadata", "--format", "{{mpris:length}}"])
    length = 0
    if rc_len == 0:
        try:
            us = int(out_len.strip())
            length = max(0, us // 1_000_000)
        except Exception:
            length = 0

    return pos, length


def set_playback_position(seconds: float):
    # playerctl accepts absolute position in seconds for many players
    s = max(0.0, float(seconds))
    return run_playerctl(["position", f"{s}"])


def get_ytmd_status(resetCache: bool = False) -> dict | None:
    # Call YTMD API for playlist_id, queue and repeat state (cached for 30 seconds)
    if (
        not hasattr(get_ytmd_status, "_cache")
        or time.time() - get_ytmd_status._cache_time > YTMD_CACHE_DELAY
        or resetCache
    ):
        rc, ytmd_data = run_ytmdesktop_api_call(["info", "state"])
        get_ytmd_status._cache = ytmd_data or {}
        get_ytmd_status._cache_time = time.time()
    else:
        ytmd_data = get_ytmd_status._cache

    rm = (
        ytmd_data.get("player", {}).get("queue", {}).get("repeatMode", 0)
        if isinstance(ytmd_data, dict)
        else 0
    )
    if rm == 0:
        repeat_state = "no"
    elif rm == 1:
        repeat_state = "all"
    elif rm == 2:
        repeat_state = "one"
    else:
        repeat_state = "no"

    playlist_id = ytmd_data.get("playlistId", "") if isinstance(ytmd_data, dict) else ""

    queue = (
        ytmd_data.get("player", {}).get("queue", {}).get("items", [])
        if isinstance(ytmd_data, dict)
        else []
    )
    # simplify queue items
    simple_queue = []
    for item in queue:
        simple_queue.append(
            {
                "title": item.get("title", ""),
                "author": item.get("author", ""),
                "videoId": item.get("videoId", ""),
                "selected": item.get("selected", False),
            }
        )

    # thumbnail_url = ( not that simple
    #    ytmd_data.get("thumbnail", "") if isinstance(ytmd_data, dict) else ""
    # )

    return {
        "repeat_state": repeat_state,
        "playlist_id": playlist_id,
        "queue": simple_queue,
        # "thumbnail_url": thumbnail_url,
    }  # type: ignore


def get_ytmd_playlist(resetCache: bool = False) -> dict | None:
    # Call YTMD API for playlist (cached for 30 minutes)
    if (
        not hasattr(get_ytmd_playlist, "_cache")
        or time.time() - get_ytmd_playlist._cache_time > YTMD_CACHE_DELAY * 60
        or resetCache
    ):
        rc, ytmd_data = run_ytmdesktop_api_call(["info", "playlists"])
        get_ytmd_playlist._cache = ytmd_data or {}
        get_ytmd_playlist._cache_time = time.time()
        print(f"{datetime.now()} YTMD data refreshed playlists count: {len(ytmd_data)}")
    else:
        ytmd_data = get_ytmd_playlist._cache

    playlists = {}
    for p in ytmd_data:
        playlists[p.get("id", "")] = p.get("title", "")

    return playlists  # type: ignore


def get_status(resetCache: bool = False) -> dict[str, str | int | float | bool]:
    rc1, out1 = run_playerctl(["status"])
    status = out1.strip() if rc1 == 0 else "Unknown"

    rc2, out2 = run_playerctl(["metadata", "--format", "{{title}}|||{{artist}}"])
    title = artist = ""
    if rc2 == 0:
        parts = out2.split("|||", 1)
        title = parts[0].strip() if len(parts) > 0 else ""
        artist = parts[1].strip() if len(parts) > 1 else ""
    vol, muted = get_system_volume()
    pos, length = get_playback_position_and_length()

    ytmd_data = get_ytmd_status(resetCache=resetCache)

    return {
        "status": status,
        "title": title,
        "artist": artist,
        "volume": vol,
        "muted": muted,
        "pos": pos,  # seconds (float)
        "length": length,  # seconds (int, 0 if unknown)
        "repeat_state": ytmd_data["repeat_state"],  # possible: "no", "one", "all"
        "playlist_id": ytmd_data["playlist_id"],  # string or empty
        "queue": ytmd_data[
            "queue"
        ],  # list of {"title":..., "author":..., "videoId":..., "selected":false/true} # type: ignore
    }


class Handler(BaseHTTPRequestHandler):
    def _send(
        self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8"
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if p == "/manifest.webmanifest":
            self._send(
                200,
                json.dumps(MANIFEST).encode("utf-8"),
                "application/manifest+json; charset=utf-8",
            )
            return
        if p == "/sw.js":
            self._send(
                200, SW_JS.encode("utf-8"), "application/javascript; charset=utf-8"
            )
            return
        if p == "/icon.svg":
            self._send(200, ICON_SVG.encode("utf-8"), "image/svg+xml; charset=utf-8")
            return
        if p == "/css/ytremote.css":
            self._send(200, CSS.encode("utf-8"), "text/css; charset=utf-8")
            return
        if p == "/js/ytremote.js":
            self._send(200, JS.encode("utf-8"), "application/javascript; charset=utf-8")
            return
        if p == "/api/status":
            self._send(
                200,
                json.dumps(get_status()).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        if p == "/api/playlists":
            # gets list of playlists
            self._send(
                200,
                json.dumps(get_ytmd_playlist()).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        self._send(404, b"Not found\n")

    def do_POST(self):
        p = urlparse(self.path).path
        mapping: dict[str, tuple[str, list[str]]] = {
            "/api/play-pause": ("playerctl", ["play-pause"]),
            "/api/next": ("playerctl", ["next"]),
            "/api/previous": ("playerctl", ["previous"]),
            "/api/vol-up": ("xdotool", ["XF86AudioRaiseVolume"]),
            "/api/vol-down": ("xdotool", ["XF86AudioLowerVolume"]),
            "/api/vol-set": ("forced_infra", []),
            "/api/mute-toggle": ("forced_infra", []),
            "/api/seek-set": ("forced_infra", []),
            "/api/photos-prev": ("xdotool_firefox", ["Left"]),
            "/api/photos-next": ("xdotool_firefox", ["Right"]),
            "/api/photos-pause": ("xdotool_firefox", ["Up"]),
            "/api/photos-playsignal": ("xdotool_firefox", ["Down"]),
            "/api/shuffle": ("ytmdesktop", ["command", "shuffle"]),
            "/api/repeat": ("forced_infra", []),
            "/api/playlist-track-set": ("forced_infra", []),
        }
        if p not in mapping:
            self._send(404, b"Not found\n")
            return
        if p == "/api/vol-set":
            # Read JSON: {"value": 0..100}
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8", "ignore"))
                val = int(data.get("value"))
            except Exception:
                self._send(400, b"Bad JSON\n")
                return

            v = max(0, min(100, val))

            # Rule:
            # - volume == 0 => mute ON
            # - volume  > 0 => mute OFF
            if v == 0:
                rc_m, out_m = run_cmd(
                    ["bash", "-lc", "pactl set-sink-mute @DEFAULT_SINK@ 1"]
                )
                if rc_m != 0:
                    self._send(500, (out_m + "\n").encode("utf-8", "ignore"))
                    return
            else:
                rc_u, out_u = run_cmd(
                    ["bash", "-lc", "pactl set-sink-mute @DEFAULT_SINK@ 0"]
                )
                if rc_u != 0:
                    self._send(500, (out_u + "\n").encode("utf-8", "ignore"))
                    return

            rc, out = run_cmd(
                ["bash", "-lc", f"pactl set-sink-volume @DEFAULT_SINK@ {v}%"]
            )
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, (out + "\n").encode("utf-8", "ignore"))
            return
        if p == "/api/mute-toggle":
            # unused (mute by volume 0), but kept for compatibility
            rc, out = run_cmd(
                ["bash", "-lc", "pactl set-sink-mute @DEFAULT_SINK@ toggle"]
            )
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, (out + "\n").encode("utf-8", "ignore"))
            return
        if p == "/api/seek-set":
            # Read JSON: {"value": seconds}
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8", "ignore"))
                val = float(data.get("value"))
            except Exception:
                self._send(400, b"Bad JSON\n")
                return

            rc, out = set_playback_position(val)
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, (out + "\n").encode("utf-8", "ignore"))
            return
        if p == "/api/repeat":
            # toggle repeat mode
            status = get_status()
            current = status.get("repeat_state", "no")
            if current == "no":
                new_mode = (
                    "1"  # all (we won't go to "one" loop, because it's less useful)
                )
            else:
                new_mode = "0"  # one

            kind, args = mapping[p]
            args = [  # type: ignore
                "command",
                "repeatMode",
                None,
                None,
                new_mode,
            ]

            rc, out = run_ytmdesktop_api_call(args)
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                msg = (f"{kind} error: " + (out or "unknown") + "\n").encode(
                    "utf-8", "ignore"
                )
                self._send(500, msg)
            get_status(resetCache=True)
            return
        if p == "/api/playlist-track-set":
            # Read JSON: {"playlistId": "...", "trackId": "..."}
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8", "ignore"))
                playlistId = str(data.get("playlistId", None))
                trackId = str(data.get("trackId", None))
            except Exception:
                self._send(400, b"Bad JSON\n")
                return

            kind, args = mapping[p]
            args = [  # type: ignore
                "command",
                "changeVideo",
                playlistId,
                trackId,
            ]

            rc, out = run_ytmdesktop_api_call(args)
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                msg = (f"{kind} error: " + (out or "unknown") + "\n").encode(
                    "utf-8", "ignore"
                )
                self._send(500, msg)
            get_status(resetCache=True)
            return

        kind, args = mapping[p]
        if kind == "playerctl":
            rc, out = run_playerctl(args)
        elif kind == "ytmdesktop":
            rc, out = run_ytmdesktop_api_call(args)  # type: ignore
            out = str(out) if out is not None else ""  # type: ignore
        elif kind == "xdotool_firefox":
            rc, out = run_xdotool_key_to_firefox(args[0])
        else:
            rc, out = run_xdotool_key(args[0])

        if rc == 0:
            self._send(200, b"OK\n")
        else:
            msg = (f"{kind} error: " + (out or "unknown") + "\n").encode(
                "utf-8", "ignore"
            )
            self._send(500, msg)

    def log_message(self, format: str, *args: Any):
        try:
            if len(args) >= 1 and "/api/status" in args[0]:
                return  # status would be too verbose
            return  # bon en fait on ne veut rien voir du tout
            super().log_message(format, *args)
        except:
            pass


if __name__ == "__main__":
    print(f"Listening on http://{HOST}:{PORT}  (Ctrl+C to stop)")
    HTTPServer((HOST, PORT), Handler).serve_forever()
