#!/usr/bin/env python3
# avec photos : Précédent / Pause / Suivant
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8000

# Si tu veux cibler un player précis, décommente et ajuste :
# PLAYER = "youtube-music-desktop-app"
# BASE_CMD = ["playerctl", "-p", PLAYER]
BASE_CMD = ["playerctl"]

APP_TITLE = "remote iMac"
THEME_COLOR = "#003366"

HTML = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="theme-color" content="{THEME_COLOR}" />
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="icon" href="/icon.svg" type="image/svg+xml">
  <title>{APP_TITLE}</title>
  <style>
    html, body {{ height: 100%; margin: 0; }}
    body{{
      background:{THEME_COLOR}; color:#fff;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, sans-serif;
      display:flex; align-items:center; justify-content:center;
      padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
    }}
    .page{{
      width:min(980px, 96vw);
      display:flex; flex-direction:column; gap:18px;
    }}
    .now{{
      background:#121212;
      border: 2px solid rgba(255,255,255,.14);
      border-radius:20px;
      padding:16px 18px;
      box-shadow: 0 12px 34px rgba(0,0,0,.45);
      min-height:92px;
      display:flex; flex-direction:column; justify-content:center;
    }}
    .title{{
      font-size: clamp(18px, 3.5vw, 30px);
      font-weight: 900;
      line-height: 1.15;
      word-break: break-word;
    }}
    .artist{{
      margin-top:6px;
      font-size: clamp(14px, 2.5vw, 18px);
      opacity:.78;
      word-break: break-word;
    }}
    .grid{{
      width:min(980px, 96vw);
      display:grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 14px;
    }}
    .grid2{{
      width:min(980px, 96vw);
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    button{{
      border: 2px solid rgba(255,255,255,.22);
      border-radius: 18px;
      background: #66A0D3;
      color: #000;
      font-size: clamp(16px, 3.2vw, 28px);
      font-weight: 900;
      letter-spacing: 0.5px;
      box-shadow: 0 14px 34px rgba(0,0,0,.45);
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
      user-select:none;
      padding: 10px 10px;          /* moins haut */
    }}
    button:active {{ transform: scale(0.985); }}
    .hint{{ text-align:center; opacity:.55; font-size:10px; margin-top:2px; }}
    .pill{{
      display:inline-block;
      padding:2px 10px;
      border-radius:999px;
      background:#1f1f1f;
      border: 1px solid rgba(255,255,255,.14);
      font-weight:900;
      margin-right:8px;
    }}
    .photos{{
      background:#000;
      border: 2px solid rgba(255,255,255,.14);
      border-radius:20px;
      padding:14px 16px;
      box-shadow: 0 12px 34px rgba(0,0,0,.45);
    }}
    .photos-title{{
      font-size: 18px;
      font-weight: 900;
      margin: 0 0 10px 0;
    }}
    .grid-photos{{
      width:100%;
      display:grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
    }}

    A:link    {{color:#aaaaaa;text-decoration: none;}}
    A:visited {{color:#808080;text-decoration: none;}}
    A:active  {{color:#ff0000;text-decoration: underline;}}
    A:hover   {{              text-decoration: underline;}}
  </style>
</head>
<body>
  <div class="page">
    <div class="now">
      <div class="title"><span class="pill" id="state">…</span><span id="track">Aucune piste</span></div>
      <div class="artist" id="artist">—</div>
    </div>
    <div class="now" style="min-height:auto">
      <div class="title">
        <span class="pill">⏱</span>
        <span id="posLabel">—:— / —:—</span>
      </div>
      <input id="pos" type="range" min="0" max="100" value="0"
            style="width:100%; margin-top:12px;"
            oninput="queueSeek(this.value)">
    </div>

    <div class="grid">
      <button onclick="send('/api/previous')">⏮</button>
      <button onclick="send('/api/play-pause')">⏯</button>
      <button onclick="send('/api/next')">⏭</button>
    </div>

    <div class="grid2">
      <button onclick="send('/api/vol-down')">🔉 −</button>
      <button onclick="send('/api/vol-up')">🔊 +</button>
    </div>

    <div class="now" style="min-height:auto">
      <div class="title">
        <span class="pill">🔊</span>
        <span id="volLabel">—%</span>
        <button style="margin-left:10px; padding:10px 14px; font-size:18px; border-radius:14px;"
                onclick="send('/api/mute-toggle')">🔇 / 🔈</button>
      </div>
      <input id="vol" type="range" min="0" max="100" value="50"
            style="width:100%; margin-top:12px;"
            oninput="queueVolume(this.value)">
    </div>

    <div class="photos">
      <div class="photos-title">Photos</div>
      <div class="grid-photos">
        <button onclick="send('/api/photos-prev')">⏮</button>
        <button onclick="send('/api/photos-pause')">⏸</button>
        <button onclick="send('/api/photos-next')">⏭</button>
      </div>
    </div>

    <div class="hint"><a href=mailto:frapi@centrale-lyon.org>Frapi</a> {APP_TITLE}<br/>
    installable<br/>
    • iOS Safari : Partager → Sur l’écran d’accueil<br/>
    • Android Chrome : Menu → Installer l’application
    </div>
  </div>

<script>

const APP_TITLE = "{APP_TITLE}";
async function send(path) {{
  try {{
    const r = await fetch(path, {{method:'POST'}});
    if(!r.ok) throw new Error(await r.text());
    if (navigator.vibrate) navigator.vibrate(15);
    await refresh();
  }} catch(e) {{
    alert("Erreur: " + e);
  }}
}}

async function refresh(){{
  try{{
    const r = await fetch('/api/status', {{cache:'no-store'}});
    if(!r.ok) throw new Error(await r.text());
    const s = await r.json();
    document.getElementById('track').textContent = s.title || "Aucune piste";
    document.getElementById('artist').textContent = s.artist || "—";
    const st = s.status || "Unknown";
    document.getElementById('state').textContent = (st === "Playing") ? "▶︎" : (st === "Paused") ? "⏸" : "…";
    if (typeof s.volume === "number") {{
      document.getElementById('vol').value = s.volume;
      document.getElementById('volLabel').textContent = `${{s.volume}}%${{s.muted ? " (muet)" : ""}}`;
    }}
    // position / durée
    if (typeof s.length === "number" && s.length > 0) {{
      const pos = (typeof s.pos === "number") ? s.pos : 0;
      document.getElementById('pos').max = s.length;
      document.getElementById('pos').value = Math.min(Math.max(0, pos), s.length);
      document.getElementById('posLabel').textContent = `${{fmtTime(pos)}} / ${{fmtTime(s.length)}}`;

      // mettre la progression dans le titre (onglet + PWA)
      document.title = `${{APP_TITLE}} — ${{s.title}} — ${{fmtTime(pos)}}/${{fmtTime(s.length)}}`;
    }} else {{
      document.getElementById('posLabel').textContent = "—:— / —:—";
      document.title = APP_TITLE;
    }}

  }} catch(e) {{}}
}}

if ('serviceWorker' in navigator) {{
  navigator.serviceWorker.register('/sw.js').catch(()=>{{}});
}}

let volTimer = null;

function queueVolume(v){{
  document.getElementById('volLabel').textContent = `${{v}}%`;
  if (volTimer) clearTimeout(volTimer);
  volTimer = setTimeout(() => setVolume(v), 120);
}}

async function setVolume(v){{
  try{{
    const r = await fetch('/api/vol-set', {{
      method:'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{value: Number(v)}})
    }});
    if(!r.ok) throw new Error(await r.text());
  }} catch(e){{
    // optionnel: alert(e)
  }}
}}

function fmtTime(sec){{
  sec = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${{m}}:${{String(s).padStart(2,'0')}}`;
}}

let seekTimer = null;

function queueSeek(v){{
  // feedback immédiat
  const cur = Number(v);
  const max = Number(document.getElementById('pos').max || 0);
  document.getElementById('posLabel').textContent =
    `${{fmtTime(cur)}} / ${{fmtTime(max)}}`;

  if (seekTimer) clearTimeout(seekTimer);
  seekTimer = setTimeout(() => setSeek(cur), 120);
}}

async function setSeek(v){{
  try{{
    const r = await fetch('/api/seek-set', {{
    method:'POST',
      headers: {{"Content-Type":'application/json'}},
      body: JSON.stringify({{value: Number(v)}})
    }});
    if(!r.ok) throw new Error(await r.text());
  }} catch(e){{
    // optionnel: alert(e)
  }}
}}

refresh();
setInterval(refresh, 1500);
</script>
</body>
</html>
"""

MANIFEST = {
    "name": APP_TITLE,
    "short_name": "remote iMac",
    "start_url": "/",
    "display": "standalone",
    "background_color": THEME_COLOR,
    "theme_color": THEME_COLOR,
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
}

SW_JS = r"""const CACHE = "ytremote-v2";
const ASSETS = ["/", "/manifest.webmanifest", "/sw.js", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(ASSETS);
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return; // always network for actions/status

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(event.request);
    if (cached) return cached;
    try {
      const res = await fetch(event.request);
      if (event.request.method === "GET" && res && res.status === 200) {
        cache.put(event.request, res.clone());
      }
      return res;
    } catch (e) {
      return (await cache.match("/")) || new Response("Offline", {status: 200});
    }
  })());
});
"""

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#0b0b0b"/>
  <path d="M165 160h50v192h-50zM297 160l-92 96 92 96v-64h50V224h-50z" fill="#fff" opacity="0.92"/>
  <path d="M358 210c18 16 18 76 0 92" stroke="#fff" stroke-width="18" fill="none" opacity="0.9" stroke-linecap="round"/>
</svg>
"""


def run_cmd(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def run_playerctl(args):
    try:
        return run_cmd(BASE_CMD + args)
    except Exception as e:
        return 1, str(e)


def run_xdotool_key(keysym):
    # Use a shell so we can "export DISPLAY=:0 && ..."
    cmd = ["bash", "-lc", f"export DISPLAY=:0; xdotool key {keysym}"]
    try:
        return run_cmd(cmd)
    except Exception as e:
        return 1, str(e)


def run_xdotool_key_to_firefox(keysym):
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
        import re

        m = re.search(r"(\d+)%", out)
        if m:
            vol = int(m.group(1))

    rc2, out2 = run_cmd(["bash", "-lc", "pactl get-sink-mute @DEFAULT_SINK@"])
    muted = False
    if rc2 == 0:
        muted = "yes" in out2.lower()

    return (vol if vol is not None else 0, muted)


def set_system_volume(value_0_100: int):
    v = max(0, min(100, int(value_0_100)))
    return run_cmd(["bash", "-lc", f"pactl set-sink-volume @DEFAULT_SINK@ {v}%"])


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


def get_status():
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
    return {
        "status": status,
        "title": title,
        "artist": artist,
        "volume": vol,
        "muted": muted,
        "pos": pos,  # seconds (float)
        "length": length,  # seconds (int, 0 if unknown)
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8"):
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
        if p == "/api/status":
            self._send(
                200,
                json.dumps(get_status()).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        self._send(404, b"Not found\n")

    def do_POST(self):
        p = urlparse(self.path).path
        mapping = {
            "/api/play-pause": ("playerctl", ["play-pause"]),
            "/api/next": ("playerctl", ["next"]),
            "/api/previous": ("playerctl", ["previous"]),
            "/api/vol-up": ("xdotool", ["XF86AudioRaiseVolume"]),
            "/api/vol-down": ("xdotool", ["XF86AudioLowerVolume"]),
            "/api/vol-set": ("pactl", []),
            "/api/mute-toggle": ("pactl", ["toggle-mute"]),
            "/api/seek-set": ("playerctl", []),
            "/api/photos-prev": ("xdotool_firefox", ["Left"]),
            "/api/photos-next": ("xdotool_firefox", ["Right"]),
            "/api/photos-pause": ("xdotool_firefox", ["Up"]),
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

            rc, out = set_system_volume(val)
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

        kind, args = mapping[p]
        if kind == "playerctl":
            rc, out = run_playerctl(args)
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

    def log_message(self, format, *args):
        if len(args) >= 1 and "/api/status" in args[0]:
            return  # status would be too verbose
        return  # bon en fait on ne veut rien voir du tout
        super().log_message(format, *args)


if __name__ == "__main__":
    print(f"Listening on http://{HOST}:{PORT}  (Ctrl+C to stop)")
    HTTPServer((HOST, PORT), Handler).serve_forever()
