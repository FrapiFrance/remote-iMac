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
from config import config
from urllib.parse import unquote
from ytm_api_client import ytmdesktop_api_call  # type: ignore

if config["playerctl_player"] is not None:
    PLAYER = config["playerctl_player"]
    BASE_CMD = ["playerctl", "-p", PLAYER]
else:
    BASE_CMD = ["playerctl"]

HOST = config["host"]
PORT = config["port"]

YTMD_CACHE_DELAY = config["youtubemusicdesktop_state_cache_delay"]  # seconds
YTMD_PLAYLISTS_CACHE_DELAY = config["youtubemusicdesktop_playlists_cache_delay"]

current_photo_image_path = None


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


# YTMD limite /state à 1 requête / 5 s et /playlists à 1 requête / 30 s (par token) :
# au-delà on reçoit un 429. On garde donc toujours le dernier état valide en cache.
YTMD_STATE_MIN_INTERVAL = 5.0
YTMD_PLAYLISTS_RETRY_DELAY = 30.0

_ytmd_state: dict[str, Any] = {"data": None, "fetched_at": 0.0, "stale": False}
_ytmd_playlists: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def _get_ytmd_raw_state() -> dict:
    s = _ytmd_state
    delay = YTMD_STATE_MIN_INTERVAL
    if not s["stale"]:
        delay = max(delay, YTMD_CACHE_DELAY)
    if time.time() - s["fetched_at"] >= delay:
        s["fetched_at"] = time.time()
        rc, data = run_ytmdesktop_api_call(["info", "state"])
        if rc == 0 and isinstance(data, dict):
            s["data"] = data
            s["stale"] = False
        # sinon (401, 429, YTMD fermé...) : on garde le dernier état valide
    return s["data"] or {}


def invalidate_ytmd_status() -> None:
    # relire /state dès que le rate limit YTMD le permet
    _ytmd_state["stale"] = True


def _patch_ytmd_queue(key: str, value: Any) -> None:
    # mise à jour "optimiste" du cache après une commande, en attendant la prochaine lecture de /state
    queue = ((_ytmd_state["data"] or {}).get("player") or {}).get("queue")
    if isinstance(queue, dict):
        queue[key] = value


def get_ytmd_status() -> dict:
    # playlist_id, queue, repeat et shuffle d'après l'API YTMD
    ytmd_data = _get_ytmd_raw_state()
    queue = (ytmd_data.get("player") or {}).get("queue") or {}

    # RepeatMode YTMD : -1 inconnu, 0 aucun, 1 tout, 2 un seul
    repeat_state = {1: "all", 2: "one"}.get(queue.get("repeatMode"), "no")

    simple_queue = []
    for item in queue.get("items") or []:
        if not isinstance(item, dict):  # YTMD 2.1 peut renvoyer des items null
            continue
        simple_queue.append(
            {
                "title": item.get("title", ""),
                "author": item.get("author", ""),
                "videoId": item.get("videoId", ""),
                "selected": bool(item.get("selected", False)),
            }
        )

    return {
        "repeat_state": repeat_state,
        "shuffle": bool(queue.get("shuffleEnabled", False)),  # fourni depuis YTMD 2.1
        "playlist_id": ytmd_data.get("playlistId") or "",
        "queue": simple_queue,
    }


def get_ytmd_playlist() -> dict[str, str]:
    # {id: titre} des playlists, en cache YTMD_PLAYLISTS_CACHE_DELAY (nouvel essai après 30 s en cas d'échec)
    s = _ytmd_playlists
    delay = (
        YTMD_PLAYLISTS_CACHE_DELAY if s["data"] is not None else YTMD_PLAYLISTS_RETRY_DELAY
    )
    if time.time() - s["fetched_at"] >= delay:
        s["fetched_at"] = time.time()
        rc, data = run_ytmdesktop_api_call(["info", "playlists"])
        if rc == 0 and isinstance(data, list):
            s["data"] = {
                p.get("id", ""): p.get("title", "") for p in data if isinstance(p, dict)
            }
            print(f"{datetime.now()} YTMD playlists refreshed, count: {len(s['data'])}")
    return s["data"] or {}


def get_status() -> dict[str, Any]:
    global config
    global current_photo_image_path
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

    ytmd_data = get_ytmd_status()
    hide_photos = config["hidePhotos"]  # type: ignore

    photo_image_path = "about:blank"
    if not hide_photos:
        try:
            with open(
                os.path.expanduser(
                    config["photoFile"]  # type: ignore
                ),
                "r",
                encoding="utf-8",
            ) as f:
                photo_image_path_candidate = f.read().strip()
                # like "modules/MMM-BackgroundSlideshow/google_photos/2022/IMG_3062.JPG"
                if "../" in photo_image_path_candidate:
                    raise ValueError("Invalid path: contains '..'")
                photo_image_path = photo_image_path_candidate
                current_photo_image_path = photo_image_path
        except Exception as e:
            print(f"{datetime.now()} photo_image_path read error: {e}")

    return {
        "status": status,
        "title": title,
        "artist": artist,
        "volume": vol,
        "muted": muted,
        "pos": pos,  # seconds (float)
        "length": length,  # seconds (int, 0 if unknown)
        "repeat_state": ytmd_data["repeat_state"],  # possible: "no", "one", "all"
        "shuffle": ytmd_data["shuffle"],  # bool
        "playlist_id": ytmd_data["playlist_id"],  # string or empty
        "queue": ytmd_data[
            "queue"
        ],  # list of {"title":..., "author":..., "videoId":..., "selected":false/true} # type: ignore
        "hide_photos": hide_photos,
        "photo_image_path": photo_image_path,
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
        p = unquote(p)
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
        # Serve photo files
        if p.startswith(
            "/" + config["photoMagicMirrorRoot"]  # type: ignore
        ):
            # far more secure : we won't take the path provided by th client, but take our local current_photo_image_path
            if current_photo_image_path:
                p = "/" + current_photo_image_path
            else:
                self._send(404, b"Not found\n")
                return

            p = p.replace(
                "/" + config["photoMagicMirrorRoot"],  # type: ignore
                config["photoRoot"],  # type: ignore
            )
            path_on_disk = os.path.expanduser(p.lstrip("/"))
            if os.path.isfile(path_on_disk):
                try:
                    if ".." in path_on_disk:
                        raise ValueError("Invalid path: contains '..'")
                    with open(path_on_disk, "rb") as f:
                        data = f.read()
                    # Simple content type detection
                    if path_on_disk.lower().endswith(
                        ".jpg"
                    ) or path_on_disk.lower().endswith(".jpeg"):
                        ctype = "image/jpeg"
                    elif path_on_disk.lower().endswith(".png"):
                        ctype = "image/png"
                    elif path_on_disk.lower().endswith(
                        ".heic"
                    ) or path_on_disk.lower().endswith(".heif"):
                        ctype = "image/heic"
                    else:
                        ctype = "application/octet-stream"
                        raise ValueError("Invalid path: not a supported image type")
                    self._send(200, data, ctype)
                    return
                except Exception as e:
                    print(f"{datetime.now()} photo file read error: {e}")
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
            "/api/shuffle": ("forced_infra", []),
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
            # bascule repeat : aucun <-> tout (on ne passe pas par "un seul", moins utile)
            current = get_ytmd_status()["repeat_state"]
            new_mode = 1 if current == "no" else 0  # entier obligatoire pour YTMD
            rc, out = run_ytmdesktop_api_call(["command", "repeatMode", None, None, new_mode])  # type: ignore
            if rc == 0:
                _patch_ytmd_queue("repeatMode", new_mode)
                invalidate_ytmd_status()
                self._send(200, b"OK\n")
            else:
                self._send(500, b"ytmdesktop error: repeatMode\n")
            return
        if p == "/api/shuffle":
            # "shuffle" mélange la file ; l'état réel (shuffleEnabled) est relu ensuite dans /state
            current = get_ytmd_status()["shuffle"]
            rc, out = run_ytmdesktop_api_call(["command", "shuffle"])
            if rc == 0:
                _patch_ytmd_queue("shuffleEnabled", not current)
                invalidate_ytmd_status()
                self._send(200, b"OK\n")
            else:
                self._send(500, b"ytmdesktop error: shuffle\n")
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
            invalidate_ytmd_status()
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
