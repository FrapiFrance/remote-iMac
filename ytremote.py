#!/usr/bin/env python3
# avec photos : Précédent / Pause / Suivant
from datetime import datetime
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from typing import Any
from urllib.parse import urlparse, unquote, parse_qs
import re
import os
import time
import requests
import shutil
import signal
import socket
import sys
from config import config
from ytm_api_client import ytmdesktop_api_call  # type: ignore

# Recherche dans YouTube Music : facultative, nécessite ytmusicapi (voir README, venv)
try:
    from ytmusicapi import YTMusic  # type: ignore
except ImportError:
    YTMusic = None

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


# LC_ALL=C : sorties en anglais, pour pouvoir les parser (pactl en français répond "Mute: oui")
CMD_ENV = {**os.environ, "LC_ALL": "C"}


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2, env=CMD_ENV)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def run_cmd_safe(cmd: list[str]) -> tuple[int, str]:
    try:
        return run_cmd(cmd)
    except Exception as e:
        return 1, str(e)


def run_playerctl(args: list[str]):
    return run_cmd_safe(BASE_CMD + args)


def run_ytmdesktop_api_call(args: list[str | None]) -> tuple[int, dict | None]:
    ok, data = ytmdesktop_api_call(*args)
    # print(f"{datetime.now()} YTMD call {args} returned ok={ok}")
    return (0 if ok else 1), data


def send_slideshow_notification(action: str) -> tuple[int, str]:
    # envoie BACKGROUNDSLIDESHOW_<action> à MagicMirror via MMM-Remote-Control
    url = f"{config['magicMirrorUrl'].rstrip('/')}/api/notification/BACKGROUNDSLIDESHOW_{action}"
    headers = {}
    if config["magicMirrorApiKey"]:
        headers["Authorization"] = f"apiKey {config['magicMirrorApiKey']}"
    try:
        r = requests.post(url, headers=headers, timeout=3)
        error = None if r.ok else f"HTTP {r.status_code} {r.text}"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    if error:
        print(f"{datetime.now()} MagicMirror {action}: {error}")
        return 1, error
    return 0, ""


def run_pactl(args: list[str]) -> tuple[int, str]:
    return run_cmd_safe(["pactl"] + args)


def get_system_volume() -> tuple[int, bool]:
    # (volume 0..100, muted)
    # ex. : "Volume: front-left: 65536 / 100% / 0.00 dB, ..."
    rc, out = run_pactl(["get-sink-volume", "@DEFAULT_SINK@"])
    m = re.search(r"(\d+)%", out) if rc == 0 else None
    vol = int(m.group(1)) if m else 0
    # ex. : "Mute: yes"
    rc2, out2 = run_pactl(["get-sink-mute", "@DEFAULT_SINK@"])
    muted = rc2 == 0 and "yes" in out2.lower()
    return vol, muted


def set_system_volume(v: int) -> tuple[int, str]:
    # volume 0..100 ; 0 => mute, > 0 => unmute
    v = max(0, min(100, int(v)))
    rc, out = run_pactl(["set-sink-mute", "@DEFAULT_SINK@", "1" if v == 0 else "0"])
    if rc != 0:
        return rc, out
    return run_pactl(["set-sink-volume", "@DEFAULT_SINK@", f"{v}%"])


def get_player_status() -> dict[str, Any]:
    # un seul appel playerctl pour statut, titre, artiste, position et durée
    # (position et mpris:length en microsecondes)
    fields = ["status", "title", "artist", "position", "mpris:length"]
    fmt = "\x1f".join("{{" + f + "}}" for f in fields)
    rc, out = run_playerctl(["metadata", "--format", fmt])
    parts = out.split("\x1f") if rc == 0 else []
    if len(parts) != len(fields):
        return {"status": "Unknown", "title": "", "artist": "", "pos": 0.0, "length": 0}
    status, title, artist, pos_us, len_us = (x.strip() for x in parts)

    def to_int(x: str) -> int:
        try:
            return max(0, int(x))
        except ValueError:
            return 0

    return {
        "status": status or "Unknown",
        "title": title,
        "artist": artist,
        "pos": to_int(pos_us) / 1_000_000,
        "length": to_int(len_us) // 1_000_000,
    }


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

# Le serveur est multi-thread : une seule lecture YTMD à la fois par cache (les autres
# requêtes reçoivent le cache sans attendre), et les bascules repeat/shuffle sont sérialisées.
_ytmd_state_lock = threading.Lock()
_ytmd_playlists_lock = threading.Lock()
_ytmd_toggle_lock = threading.Lock()


def _get_ytmd_raw_state() -> dict:
    s = _ytmd_state
    delay = YTMD_STATE_MIN_INTERVAL
    if not s["stale"]:
        delay = max(delay, YTMD_CACHE_DELAY)
    if time.time() - s["fetched_at"] >= delay and _ytmd_state_lock.acquire(blocking=False):
        try:
            s["fetched_at"] = time.time()
            rc, data = run_ytmdesktop_api_call(["info", "state"])
            if rc == 0 and isinstance(data, dict):
                s["data"] = data
                s["stale"] = False
            # sinon (401, 429, YTMD fermé...) : on garde le dernier état valide
        finally:
            _ytmd_state_lock.release()
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
    if time.time() - s["fetched_at"] >= delay and _ytmd_playlists_lock.acquire(blocking=False):
        try:
            s["fetched_at"] = time.time()
            rc, data = run_ytmdesktop_api_call(["info", "playlists"])
            if rc == 0 and isinstance(data, list):
                s["data"] = {
                    p.get("id", ""): p.get("title", "") for p in data if isinstance(p, dict)
                }
                print(f"{datetime.now()} YTMD playlists refreshed, count: {len(s['data'])}")
        finally:
            _ytmd_playlists_lock.release()
    return s["data"] or {}


# location="FR" : résultats pour la France. Ne pas mettre language="fr" : ytmusicapi repère
# les sections de résultats par leur titre anglais, et les recherches filtrées reviennent vides.
SEARCH_LOCATION = "FR"
SEARCH_LIMIT = 20
SEARCH_FILTERS = {"songs", "albums", "playlists"}
_ytmusic = None
_ytmusic_lock = threading.Lock()


def search_music(query: str, kind: str) -> list[dict[str, str]]:
    # résultats simplifiés : title, subtitle, et videoId (morceau) ou playlistId (album, playlist)
    global _ytmusic
    with _ytmusic_lock:
        if _ytmusic is None:
            _ytmusic = YTMusic(location=SEARCH_LOCATION)  # type: ignore
        ytm = _ytmusic
    results = []
    # limit n'est qu'un minimum pour ytmusicapi, d'où la coupe
    for r in ytm.search(query, filter=kind, limit=SEARCH_LIMIT)[:SEARCH_LIMIT]:
        artists = ", ".join(a.get("name", "") for a in r.get("artists") or [] if a.get("name"))
        if kind == "songs" and r.get("videoId"):
            album = (r.get("album") or {}).get("name") or ""
            results.append({
                "title": r.get("title", ""),
                "subtitle": " · ".join(x for x in (artists, album, r.get("duration") or "") if x),
                "videoId": r["videoId"],
            })
        elif kind == "albums" and r.get("playlistId"):
            results.append({
                "title": r.get("title", ""),
                "subtitle": " · ".join(x for x in (artists, r.get("year") or "") if x),
                "playlistId": r["playlistId"],
            })
        elif kind == "playlists" and str(r.get("browseId", "")).startswith("VL"):
            # browseId = "VL" + playlistId
            results.append({
                "title": r.get("title", ""),
                "subtitle": r.get("author") or "",
                "playlistId": r["browseId"][2:],
            })
    return results


def play_from_search(video_id: str | None, playlist_id: str | None, mode: str) -> tuple[int, Any]:
    # mode "play" : lecture immédiate ; "next" : ajout dans la file juste après le morceau en cours
    if mode == "play":
        return run_ytmdesktop_api_call(["command", "changeVideo", playlist_id, video_id])
    queue = ((_get_ytmd_raw_state().get("player") or {}).get("queue")) or {}
    items = queue.get("items") or []
    selected = queue.get("selectedItemIndex", -1)
    index = selected + 1 if isinstance(selected, int) and 0 <= selected < len(items) else len(items)
    # YTMD veut soit videoId, soit playlistId, pas les deux
    data: dict[str, Any] = {"videoId": video_id} if video_id else {"playlistId": playlist_id}
    data["index"] = index
    return run_ytmdesktop_api_call(["command", "queueAdd", None, None, data])  # type: ignore


# ===== Radios en direct, lues par mpv (pas par YTMD)
RADIOS = [  # (id, nom affiché), dans l'ordre de passage avec précédent / suivant
    ("franceinter", "France Inter"),
    ("franceinfo", "franceinfo"),
    ("franceculture", "France Culture"),
    ("francemusique", "France Musique"),
    ("radioclassique", "Radio Classique"),
    ("fip", "FIP"),
    ("mouv", "Mouv'"),
]
RADIO_NAMES = dict(RADIOS)
RADIO_FRANCE_URL = "https://icecast.radiofrance.fr/{}-hifi.aac?id=radiofrance"
RADIO_URLS = {
    "radioclassique": "https://radioclassique.ice.infomaniak.ch/radioclassique-high.mp3",
}  # les autres : flux Radio France
# émission ou morceau en cours :
# - Radio France : API "livemeta" (non documentée), par n° de station
# - les autres : métadonnées ICY du flux (StreamTitle), demandées à mpv
LIVEMETA_URL = "https://api.radiofrance.fr/livemeta/pull/{}"
LIVEMETA_IDS = {"franceinter": 1, "franceinfo": 2, "francemusique": 4,
                "franceculture": 5, "mouv": 6, "fip": 7}
MPV = shutil.which("mpv")  # sans mpv, pas de radios
# socket de contrôle de mpv (JSON IPC), pour lire le titre ICY
MPV_SOCKET = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "ytremote-mpv.sock")

# station : id de la radio en cours (même en pause), None hors mode radio
_radio: dict[str, Any] = {"station": None, "proc": None}
_radio_lock = threading.Lock()


def _radio_stop_proc() -> None:
    proc = _radio["proc"]
    _radio["proc"] = None
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def radio_play(station: str) -> None:
    # lance (ou relance) une station ; met YTMD en pause
    with _radio_lock:
        _radio_stop_proc()
        if _radio["station"] is None:
            run_playerctl(["pause"])
        _radio["station"] = station
        # avec le paquet mpv-mpris, mpv apparaît dans KDE (touches multimédia, lecteur de la
        # barre des tâches) sous le nom de la station ; playerctl_player garde YTMD pour le reste
        _radio["proc"] = subprocess.Popen(
            [MPV, "--no-video", "--really-quiet", f"--input-ipc-server={MPV_SOCKET}",
             f"--force-media-title={RADIO_NAMES[station]}",
             RADIO_URLS.get(station) or RADIO_FRANCE_URL.format(station)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def _radio_playing() -> bool:
    # mpv tourne, et n'a pas été mis en pause au clavier (MPRIS, si mpv-mpris est installé)
    proc = _radio["proc"]
    if proc is None or proc.poll() is not None:
        return False
    rc, out = run_cmd_safe(["playerctl", "-p", "mpv", "status"])
    return not (rc == 0 and out.strip() == "Paused")


def radio_toggle() -> None:
    # en direct, une pause n'a pas de sens : on coupe, et on relance le direct
    # (y compris après une pause au clavier, pour repartir du direct et non du tampon)
    with _radio_lock:
        playing = _radio_playing()
        station = _radio["station"]
        _radio_stop_proc()
    if not playing and station:
        radio_play(station)


def radio_zap(step: int) -> None:
    # précédent / suivant : station voisine dans RADIOS
    ids = [r[0] for r in RADIOS]
    station = _radio["station"]
    i = ids.index(station) if station in ids else 0
    radio_play(ids[(i + step) % len(ids)])


def radio_exit() -> None:
    # retour à YTMD (choix d'une playlist, d'un morceau...)
    with _radio_lock:
        _radio_stop_proc()
        _radio["station"] = None


_livemeta: dict[str, Any] = {"station": None, "text": "", "until": 0.0}
_livemeta_lock = threading.Lock()


def _fetch_livemeta(station: str) -> tuple[str, float]:
    # (texte à afficher, date jusqu'à laquelle il reste valable)
    now = time.time()
    try:
        data = requests.get(LIVEMETA_URL.format(LIVEMETA_IDS[station]), timeout=3).json()
    except Exception as e:
        print(f"{datetime.now()} livemeta {station}: {type(e).__name__}: {e}")
        return "", now + 60
    current = [
        st for st in (data.get("steps") or {}).values()
        if st.get("start", 0) <= now < st.get("end", 0)
    ]
    if not current:
        return "", now + 30
    # le plus détaillé : morceau (depth 3) > partie d'émission > émission (depth 1)
    step = max(current, key=lambda st: st.get("depth", 0))
    if step.get("embedType") == "song":
        who = step.get("authors") or ", ".join(step.get("highlightedArtists") or [])
        parts = (step.get("title"), who)
    else:
        parts = (step.get("titleConcept"), step.get("title"))
    text = " · ".join(x.strip() for x in parts if x and x.strip())
    # relire à la fin de l'étape en cours, et au moins chaque minute
    until = min(now + 60, min(st["end"] for st in current) + 2)
    return text, until


def _mpv_icy_title() -> str:
    # titre ICY du flux en cours, demandé à mpv par sa socket JSON IPC ; "" si indisponible
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            sock.connect(MPV_SOCKET)
            sock.sendall(b'{"command": ["get_property", "metadata/by-key/icy-title"]}\n')
            buf = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    return ""
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    msg = json.loads(line)
                    if "error" in msg:  # la réponse (les autres lignes sont des événements)
                        data = msg.get("data")
                        return data.strip() if msg["error"] == "success" and isinstance(data, str) else ""
    except (OSError, ValueError):
        return ""


def radio_now_playing(station: str) -> str:
    if station not in LIVEMETA_IDS:
        return _mpv_icy_title()
    c = _livemeta
    stale = c["station"] != station or time.time() >= c["until"]
    if stale and station in LIVEMETA_IDS and _livemeta_lock.acquire(blocking=False):
        try:
            text, until = _fetch_livemeta(station)
            c.update(station=station, text=text, until=until)
        finally:
            _livemeta_lock.release()
    return c["text"] if c["station"] == station else ""


def radio_status() -> dict[str, Any] | None:
    station = _radio["station"]
    if station is None:
        return None
    return {
        "id": station,
        "name": RADIO_NAMES.get(station, station),
        "playing": _radio_playing(),
        "now": radio_now_playing(station),  # émission ou morceau en cours, ou ""
    }


def get_status() -> dict[str, Any]:
    global config
    global current_photo_image_path
    player = get_player_status()
    vol, muted = get_system_volume()

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

    radio = radio_status()
    if radio:
        # en mode radio, l'état vient de mpv ; YTMD est en pause derrière
        player = {
            "status": "Playing" if radio["playing"] else "Paused",
            "title": radio["name"],
            "artist": radio["now"] or "Radio en direct",
            "pos": 0.0,
            "length": 0,
        }

    return {
        "status": player["status"],
        "title": player["title"],
        "artist": player["artist"],
        "volume": vol,
        "muted": muted,
        "pos": player["pos"],  # seconds (float)
        "length": player["length"],  # seconds (int, 0 if unknown)
        "repeat_state": ytmd_data["repeat_state"],  # possible: "no", "one", "all"
        "shuffle": ytmd_data["shuffle"],  # bool
        "playlist_id": ytmd_data["playlist_id"],  # string or empty
        "queue": ytmd_data[
            "queue"
        ],  # list of {"title":..., "author":..., "videoId":..., "selected":false/true} # type: ignore
        "hide_photos": hide_photos,
        "search": YTMusic is not None,  # recherche disponible (ytmusicapi installé)
        "radio": radio,  # None, ou {"id", "name", "playing"}
        "radios": [{"id": i, "name": n} for i, n in RADIOS] if MPV else [],
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
        if p == "/api/search":
            # /api/search?q=...&type=songs|albums|playlists
            if YTMusic is None:
                self._send(503, b"ytmusicapi absent : recherche indisponible\n")
                return
            qs = parse_qs(urlparse(self.path).query)
            query = qs.get("q", [""])[0].strip()
            kind = qs.get("type", ["songs"])[0]
            if not query or kind not in SEARCH_FILTERS:
                self._send(400, b"Bad request\n")
                return
            try:
                results = search_music(query, kind)
            except Exception as e:
                print(f"{datetime.now()} search error: {type(e).__name__}: {e}")
                self._send(502, f"Erreur de recherche : {e}\n".encode("utf-8", "ignore"))
                return
            self._send(
                200,
                json.dumps(results).encode("utf-8"),
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
            "/api/vol-set": ("forced_infra", []),
            "/api/mute-toggle": ("forced_infra", []),
            "/api/seek-set": ("forced_infra", []),
            # pause totale : c'est "suivante" qui relance le diaporama
            "/api/photos-prev": ("slideshow", ["PREVIOUS"]),
            "/api/photos-next": ("slideshow", ["NEXT"]),
            "/api/photos-pause": ("slideshow", ["PAUSE"]),
            "/api/photos-playsignal": ("slideshow", ["SIGNAL_PHOTO"]),
            "/api/shuffle": ("forced_infra", []),
            "/api/repeat": ("forced_infra", []),
            "/api/playlist-track-set": ("forced_infra", []),
            "/api/search-play": ("forced_infra", []),
            "/api/radio": ("forced_infra", []),
        }
        if p not in mapping:
            self._send(404, b"Not found\n")
            return
        if p == "/api/radio":
            # Read JSON: {"id": "franceculture"}
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                station = json.loads(raw.decode("utf-8", "ignore")).get("id")
            except Exception:
                station = None
            if not MPV or station not in RADIO_NAMES:
                self._send(400, b"Radio inconnue, ou mpv absent\n")
                return
            radio_play(station)
            self._send(200, b"OK\n")
            return
        if _radio["station"] is not None:
            # mode radio : lecture et précédent / suivant pilotent mpv ;
            # aléatoire, répéter et position n'ont pas de sens en direct
            if p == "/api/play-pause":
                radio_toggle()
                self._send(200, b"OK\n")
                return
            if p in ("/api/next", "/api/previous"):
                radio_zap(1 if p == "/api/next" else -1)
                self._send(200, b"OK\n")
                return
            if p in ("/api/shuffle", "/api/repeat", "/api/seek-set"):
                self._send(409, b"Radio en direct\n")
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

            rc, out = set_system_volume(val)
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, (out + "\n").encode("utf-8", "ignore"))
            return
        if p == "/api/mute-toggle":
            rc, out = run_pactl(["set-sink-mute", "@DEFAULT_SINK@", "toggle"])
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
            with _ytmd_toggle_lock:
                current = get_ytmd_status()["repeat_state"]
                new_mode = 1 if current == "no" else 0  # entier obligatoire pour YTMD
                rc, out = run_ytmdesktop_api_call(["command", "repeatMode", None, None, new_mode])  # type: ignore
                if rc == 0:
                    _patch_ytmd_queue("repeatMode", new_mode)
                    invalidate_ytmd_status()
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, b"ytmdesktop error: repeatMode\n")
            return
        if p == "/api/shuffle":
            # "shuffle" mélange la file ; l'état réel (shuffleEnabled) est relu ensuite dans /state
            with _ytmd_toggle_lock:
                current = get_ytmd_status()["shuffle"]
                rc, out = run_ytmdesktop_api_call(["command", "shuffle"])
                if rc == 0:
                    _patch_ytmd_queue("shuffleEnabled", not current)
                    invalidate_ytmd_status()
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, b"ytmdesktop error: shuffle\n")
            return
        if p == "/api/search-play":
            # Read JSON: {"videoId": "..."} ou {"playlistId": "..."}, et "mode": "play" | "next"
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8", "ignore"))
                video_id = data.get("videoId") or None
                playlist_id = data.get("playlistId") or None
                mode = data.get("mode", "play")
                if not (video_id or playlist_id) or mode not in ("play", "next"):
                    raise ValueError
            except Exception:
                self._send(400, b"Bad JSON\n")
                return
            if mode == "play":
                radio_exit()
            rc, out = play_from_search(video_id, playlist_id, mode)
            invalidate_ytmd_status()
            if rc == 0:
                self._send(200, b"OK\n")
            else:
                self._send(500, f"ytmdesktop error: {mode}\n".encode())
            return
        if p == "/api/playlist-track-set":
            radio_exit()
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
        else:  # slideshow
            rc, out = send_slideshow_notification(args[0])

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
    # multi-thread : un /api/status lent (playerctl, pactl, YTMD) ne bloque plus les boutons
    # un kill (SIGTERM) passe aussi par le finally ci-dessous
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    finally:
        radio_exit()  # ne pas laisser mpv jouer tout seul
