
async function send(path) {
  try {
    const r = await fetch(path, {method:'POST'});
    if(!r.ok) throw new Error(await r.text());
    if (navigator.vibrate) navigator.vibrate(15);
    await refresh();
  } catch(e) {
    alert("Erreur: " + e);
  }
}

async function refresh(){
  try{
    const r = await fetch('/api/status', {cache:'no-store'});
    if(!r.ok) throw new Error(await r.text());
    const s = await r.json();
    document.getElementById('track').textContent = s.title || "Aucune piste";
    document.getElementById('artist').textContent = s.artist || "—";

    // état play/pause
    const st = s.status || "Unknown";
    const btnPlay = document.querySelector(".btn-primary");
    if (st === "Playing") {
      btnPlay.innerHTML = '<i class="fa-solid fa-play"></i>';
    } else if (st === "Paused") {
      btnPlay.innerHTML = '<i class="fa-solid fa-pause"></i>';
    } else {
      btnPlay.innerHTML = '<i class="fa-solid fa-ellipsis"></i>';
    }

    // état volume
    const btnVolume = document.getElementById("btnVolume");
    document.getElementById('vol').value = s.volume;
    document.getElementById('volLabel').textContent = `${s.volume}%${s.muted ? " (muet)" : ""}`;
    if (s.muted || s.volume === 0) {
      btnVolume.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
    } else {
      btnVolume.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    }

    //etat repeat
    const btnRepeat = document.getElementById("btnRepeat");
    const repeatState = s.repeat_state || "no";
    if (repeatState === "no") {
      btnRepeat.classList.add("off");
    } else {
      btnRepeat.classList.remove("off");  // on ne distingue pas "one" et "all" visuellement
    }
    // TODO etat shuffle
    //const btnShuffle = document.getElementById("btnShuffle");
    //const shuffleState = s.shuffle_state || "off";
    //if (shuffleState === "off") {
    //  btnShuffle.classList.add("off");
    //} else {
    //  btnShuffle.classList.remove("off");
    //}

    // position / durée
    if (typeof s.length === "number" && s.length > 0) {
      const pos = (typeof s.pos === "number") ? s.pos : 0;
      document.getElementById('pos').max = s.length;
      document.getElementById('pos').value = Math.min(Math.max(0, pos), s.length);
      document.getElementById('posLabel').textContent = `${fmtTime(pos)} / ${fmtTime(s.length)}`;
      // mettre la progression dans le titre (onglet + PWA)
      document.title = `remote iMac — ${s.title} — ${fmtTime(pos)}/${fmtTime(s.length)}`;
    } else {
      document.getElementById('posLabel').textContent = "—:— / —:—";
      document.title = "remote iMac — " + (s.title || "Aucune piste");
    }

    // état playlist
    if (typeof window.currentPlaylistIdLastForced === "number") {
      // si on a forcé une playlist récemment, on ne met pas à jour
      //  (car /api/status renvoie une version cachée 30 secondes)
      // console.log("have last forced timestamp:", window.currentPlaylistIdLastForced);
      const elapsed = Date.now() - window.currentPlaylistIdLastForced;
      if (elapsed < 31000) {
        // console.log("skip playlist id update, forced recently");
      } else {
        // console.log("clear last forced timestamp");
        window.currentPlaylistIdLastForced = null;
        window.currentPlaylistId = s.playlist_id || null;
      }
    } else {
      // console.log("normal playlist id update");
      window.currentPlaylistId = s.playlist_id || null;
    }
    await uiUpdatePlaylistLabel();

    // etat queue
    window.currentQueue = s.queue || []; // list of {"title":..., "author":..., "videoId":..., "selected":false/true}
    const qOverlay = document.getElementById("qOverlay");
    if (qOverlay && qOverlay.classList.contains("show")) {
      uiRenderQueue();
    }

  } catch(e) {}
  }

function toggleRepeat(){
    const btnRepeat = document.getElementById("btnRepeat");
    if (btnRepeat.classList.contains("off"))
        btnRepeat.classList.remove("off");
    else
        btnRepeat.classList.add("off");
    send('/api/repeat');
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(()=>{});
}

let volTimer = null;

function queueVolume(v){
  document.getElementById('volLabel').textContent = `${v}%`;
  if (volTimer) clearTimeout(volTimer);
  volTimer = setTimeout(() => setVolume(v), 120);
}

async function setVolume(v){
  try{
    const r = await fetch('/api/vol-set', {
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({value: Number(v)})
    });
    if(!r.ok) throw new Error(await r.text());
  } catch(e){
    // optionnel: alert(e)
  }
}

function fmtTime(sec){
  sec = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2,'0')}`;
}

let seekTimer = null;

function queueSeek(v){
  // feedback immédiat
  const cur = Number(v);
  const max = Number(document.getElementById('pos').max || 0);
  document.getElementById('posLabel').textContent =
    `${fmtTime(cur)} / ${fmtTime(max)}`;

  if (seekTimer) clearTimeout(seekTimer);
  seekTimer = setTimeout(() => setSeek(cur), 120);
}
async function setSeek(v){
  try{
    const r = await fetch('/api/seek-set', {
    method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({value: Number(v)})
    });
    if(!r.ok) throw new Error(await r.text());
  } catch(e){
    // optionnel: alert(e)
  }
}

document
  .querySelector("#volOverlay .overlay-card")
  .addEventListener("click", function (e) {
    e.stopPropagation();
  });

function uiShowTab(which) {
  const musicBtn = document.getElementById("tabbtn-music");
  const photosBtn = document.getElementById("tabbtn-photos");
  const music = document.getElementById("tab-music");
  const photos = document.getElementById("tab-photos");

  const isMusic = which === "music";
  musicBtn.classList.toggle("active", isMusic);
  photosBtn.classList.toggle("active", !isMusic);
  musicBtn.setAttribute("aria-selected", String(isMusic));
  photosBtn.setAttribute("aria-selected", String(!isMusic));
  music.classList.toggle("active", isMusic);
  photos.classList.toggle("active", !isMusic);

  // close overlays when switching
  const volOverlay = document.getElementById("volOverlay");
  if (volOverlay) {
    volOverlay.classList.remove("show");
    volOverlay.setAttribute("aria-hidden", "true");
  }
}

function uiToggleVolume() {
  const el = document.getElementById("volOverlay");
  if (!el) return;
  const show = !el.classList.contains("show");
  el.classList.toggle("show", show);
  el.setAttribute("aria-hidden", String(!show));
}

(function () {
  const btn = document.getElementById("btnVolume");
  if (!btn) return;

  let longPressTimer = null;
  let longPressed = false;
  const LONG_PRESS_MS = 500;

  // TOUCH (mobile)
  btn.addEventListener("touchstart", (e) => {
    longPressed = false;
    longPressTimer = setTimeout(() => {
      longPressed = true;
      queueVolume(0);           // MUTE
    }, LONG_PRESS_MS);
  }, { passive: true });

  btn.addEventListener("touchend", () => {
    clearTimeout(longPressTimer);
  });

  btn.addEventListener("touchcancel", () => {
    clearTimeout(longPressTimer);
  });

  // CLICK (desktop + tap court mobile)
  btn.addEventListener("click", (e) => {
    if (longPressed) {
      // on empêche le click après un long press
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    uiToggleVolume();           // TAP NORMAL
  });
})();


function uiToggleQueue() {
  const overlay = document.getElementById("qOverlay");
  if (!overlay) return;

  const show = !overlay.classList.contains("show");
  overlay.classList.toggle("show", show);
  overlay.setAttribute("aria-hidden", String(!show));

  if (show) uiRenderQueue();
}

function uiRenderQueue() {
  const listEl = document.getElementById("qlist");
  if (!listEl) return;

  const q = window.currentQueue || [];
  if (!q.length) {
    listEl.innerHTML = '<div style="opacity:.7">File vide</div>';
    return;
  }

  listEl.innerHTML = "";
  for (const item of q) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "qitem" + (item.selected ? " selected" : "");

    btn.innerHTML = `
      <div class="qtitle">${escapeHtml(item.title || item.videoId || "—")}</div>
      <div class="qauthor">${escapeHtml(item.author || "")}</div>
    `;

    btn.addEventListener("click", () => uiSelectQueueItem(item.videoId));
    listEl.appendChild(btn);
  }

  // option: auto-scroll sur l’item selected
  const sel = listEl.querySelector(".qitem.selected");
  if (sel) sel.scrollIntoView({ block: "center" });
}

async function uiSelectQueueItem(videoId) {
  if (!videoId) return;

  try {
    const r = await fetch("/api/playlist-track-set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({  trackId: videoId }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);

    // feedback optimiste: marquer selected localement (en attendant le refresh)
    if (Array.isArray(window.currentQueue)) {
      for (const it of window.currentQueue) it.selected = (it.videoId === videoId);
    }
    uiRenderQueue();
    uiToggleQueue(); // ferme l’overlay après sélection
  } catch (e) {
    alert("Impossible de sélectionner ce morceau",e);
  }
}

// petit helper pour éviter d’injecter du HTML depuis les titres
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

async function uiTogglePlaylists() {
  const overlay = document.getElementById("plOverlay");
  if (!overlay) return;

  const show = !overlay.classList.contains("show");
  overlay.classList.toggle("show", show);
  overlay.setAttribute("aria-hidden", String(!show));

  if (show) {
    await uiLoadPlaylists();
  }
}

async function uiUpdatePlaylistLabel() {
  const el = document.getElementById("playlist");
  if (!el) return;

  const id = window.currentPlaylistId;
  if (!id) {
    el.textContent = "—";
    return;
  }

  try {
    const title = window.playlistsById[id];
    // console.log("normal playlist id update:", id, title);
    el.textContent = title; 
  } catch (e) {
    // si pas trouvé, recharger la liste des playlists
    // console.log("playlist id not found, reloading playlists for ", id);
    await getPlaylists();
    try {
      const title = window.playlistsById[id];
      el.textContent = title; 
    } catch (e) {
      // console.log("still not found playlist id:", id);
      el.textContent = id; // fallback si pas réussi à charger la liste
    }
  }
}


async function getPlaylists() {
  let data;
  try {
    const r = await fetch("/api/playlists", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    data = await r.json(); // dict id -> title
    window.playlistsById = data || {};

  } catch (e) {
    listEl.innerHTML = '<div style="opacity:.7">Erreur chargement playlists</div>';
    return;
  }
}

async function uiLoadPlaylists() {
  const listEl = document.getElementById("plist");
  if (!listEl) return;

  listEl.innerHTML = '<div style="opacity:.7">Chargement…</div>';

  await getPlaylists();

  const current = window.currentPlaylistId;
  const entries = Object.entries(window.playlistsById || {}); // [[id,title],...]

  // Optionnel : tri alpha par titre
  entries.sort((a,b) => String(a[1]).localeCompare(String(b[1]), "fr", { sensitivity: "base" }));

  listEl.innerHTML = "";
  for (const [id, title] of entries) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = title || id;
    if (current && String(id) === String(current)) btn.classList.add("selected");
    btn.addEventListener("click", () => uiSelectPlaylist(id));
    listEl.appendChild(btn);
  }
}

async function uiSelectPlaylist(id) {
  try {
    const r = await fetch("/api/playlist-track-set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ playlistId: id }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);

    // Mise à jour “optimiste” : on reflète la sélection immédiatement
    window.currentPlaylistId = id;
    window.currentPlaylistIdLastForced = Date.now();
    await uiUpdatePlaylistLabel();

    // quand changement de playlist, le suffle et le repeat reviennent à off
    const btnRepeat = document.getElementById("btnRepeat");
    btnRepeat.classList.add("off");
    const btnShuffle = document.getElementById("btnShuffle");
    btnShuffle.classList.add("off");

    // Fermer overlay
    uiTogglePlaylists();
  } catch (e) {
    // Option: afficher une mini erreur
    alert("Impossible de sélectionner la playlist",e);
  }
}

(function () {
  const overlay = document.getElementById("plOverlay");
  if (!overlay) return;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) uiTogglePlaylists();
  });
})();

(function () {
  const overlay = document.getElementById("qOverlay");
  if (!overlay) return;

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) uiToggleQueue();
  });
})();

(function () {
  const overlay = document.getElementById("volOverlay");
  if (!overlay) return;

  // clic sur le fond sombre => fermer
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) {
      overlay.classList.remove("show");
      overlay.setAttribute("aria-hidden", "true");
    }
  });
})();


window.currentPlaylistIdLastForced = null;

refresh();
setInterval(refresh, 1500);
