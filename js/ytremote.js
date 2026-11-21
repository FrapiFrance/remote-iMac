const YTMD_CACHE_DELAY = 5000; // ms idem to ytremote.py
let current_photo_image_path = null;

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

    // shall we show the photos section?
    const photosSection = document.getElementById("photosSection");
    if (photosSection) {
      if (!s.hide_photos) {
        photosSection.style.display = "block";
      } else {
        photosSection.style.display = "none";
      }
    }

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
    if (typeof s.volume === "number") {
      const vol = Math.max(0, Math.min(100, Math.round(s.volume)));
      const volEl = document.getElementById("vol");
      if (volEl && document.activeElement !== volEl) volEl.value = String(vol);
      const lbl = document.getElementById("volLabel");
      if (lbl) lbl.textContent = vol + "%";
    }

    const muted = !!s.muted || (typeof s.volume === "number" && s.volume === 0);
    const icon = document.getElementById("volIcon");
    if (icon) {
      icon.className = muted ? "fa-solid fa-volume-xmark" : "fa-solid fa-volume-high";
    }

    //etat repeat
    const btnRepeat = document.getElementById("btnRepeat");
    const repeatState = s.repeat_state || "no";
    if (repeatState === "no") {
      btnRepeat.classList.add("off");
    } else {
      btnRepeat.classList.remove("off");  // on ne distingue pas "one" et "all" visuellement
    }
    // état shuffle (shuffleEnabled, fourni par YTMD >= 2.1)
    const btnShuffle = document.getElementById("btnShuffle");
    btnShuffle.classList.toggle("off", !s.shuffle);

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
      //  (car /api/status renvoie une version cachée 5 secondes)
      // console.log("have last forced timestamp:", window.currentPlaylistIdLastForced);
      const elapsed = Date.now() - window.currentPlaylistIdLastForced;
      if (elapsed < 5000) {
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
    // mode radio : station en cours (ou null), et liste des radios disponibles
    window.currentRadio = s.radio || null;
    window.radios = s.radios || [];
    const isRadio = !!window.currentRadio;
    for (const id of ["btnShuffle", "btnRepeat"]) {
      const b = document.getElementById(id);
      b.disabled = isRadio;
      if (isRadio) b.classList.add("off");
    }
    document.getElementById("pos").disabled = isRadio;

    await uiUpdatePlaylistLabel();

    // recherche disponible (ytmusicapi installé côté serveur)
    document.getElementById("btnSearch").hidden = !s.search;

    // etat queue
    window.currentQueue = s.queue || []; // list of {"title":..., "author":..., "videoId":..., "selected":false/true}
    const qOverlay = document.getElementById("qOverlay");
    if (qOverlay && qOverlay.classList.contains("show")) {
      uiRenderQueue();
    }

    // photo URL
    try {
      const photoEl = document.getElementById("photo");
      if (photoEl) {
        if (s.photo_image_path && s.photo_image_path !== current_photo_image_path) {
          current_photo_image_path = s.photo_image_path;
          photoEl.src = s.photo_image_path;
        }
        else if (!(s.photo_image_path)) {
          if (photoEl.src) {
            photoEl.src = "";
          }
        }
      }
    } catch(e) {}
  } catch(e){
    console.error("refresh error:", e);
  }
  }

function toggleShuffle(){
    // affichage immédiat, confirmé ensuite par /api/status
    document.getElementById("btnShuffle").classList.toggle("off");
    send('/api/shuffle');
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

  if (window.currentRadio) {
    listEl.innerHTML = "";
    const div = document.createElement("div");
    div.className = "qitem selected";
    div.innerHTML = `
      <div class="qtitle"><i class="fa-solid fa-tower-broadcast"></i> Radio en direct</div>
      <div class="qauthor">${escapeHtml(window.currentRadio.name)}</div>
    `;
    listEl.appendChild(div);
    return;
  }

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
  // trop chiant !
  // const sel = listEl.querySelector(".qitem.selected");
  // if (sel) sel.scrollIntoView({ block: "center" });
}

async function uiSelectQueueItem(videoId) {
  if (!videoId) return;

  try {
    const r = await fetch("/api/playlist-track-set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({  trackId: videoId, playlistId: window.currentPlaylistId  }),
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

// ===== Recherche (YouTube Music, via ytmusicapi côté serveur)
let searchKind = "songs";

function uiToggleSearch() {
  const overlay = document.getElementById("sOverlay");
  if (!overlay) return;

  const show = !overlay.classList.contains("show");
  overlay.classList.toggle("show", show);
  overlay.setAttribute("aria-hidden", String(!show));

  if (show) document.getElementById("searchInput").focus();
}

function uiSearchKind(btn) {
  searchKind = btn.dataset.kind;
  for (const b of btn.parentElement.children) b.classList.toggle("active", b === btn);
  if (document.getElementById("searchInput").value.trim()) uiSearch();
}

async function uiSearch() {
  const input = document.getElementById("searchInput");
  const listEl = document.getElementById("slist");
  const q = input.value.trim();
  if (!q) return;
  input.blur(); // referme le clavier du téléphone

  listEl.innerHTML = '<div style="opacity:.7">Recherche…</div>';
  try {
    const r = await fetch(`/api/search?type=${searchKind}&q=${encodeURIComponent(q)}`, { cache: "no-store" });
    if (!r.ok) throw new Error(await r.text());
    uiRenderSearch(await r.json());
  } catch (e) {
    listEl.innerHTML = "";
    const err = document.createElement("div");
    err.style.opacity = ".7";
    err.textContent = "Erreur : " + e.message;
    listEl.appendChild(err);
  }
}

function uiRenderSearch(results) {
  const listEl = document.getElementById("slist");
  if (!results.length) {
    listEl.innerHTML = '<div style="opacity:.7">Aucun résultat</div>';
    return;
  }

  listEl.innerHTML = "";
  for (const item of results) {
    const row = document.createElement("div");
    row.className = "qitem sitem";
    row.innerHTML = `
      <div class="stext">
        <div class="qtitle">${escapeHtml(item.title || "—")}</div>
        <div class="qauthor">${escapeHtml(item.subtitle || "")}</div>
      </div>
      <button type="button" class="btn-close" aria-label="Lire maintenant"><i class="fa-solid fa-play"></i></button>
      <button type="button" class="btn-close" aria-label="À la suite"><i class="fa-solid fa-plus"></i></button>
    `;
    const [btnPlay, btnNext] = row.querySelectorAll("button");
    btnPlay.addEventListener("click", () => uiPlayFromSearch(item, "play", btnPlay));
    btnNext.addEventListener("click", () => uiPlayFromSearch(item, "next", btnNext));
    listEl.appendChild(row);
  }
}

async function uiPlayFromSearch(item, mode, btn) {
  try {
    const r = await fetch("/api/search-play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ videoId: item.videoId, playlistId: item.playlistId, mode }),
    });
    if (!r.ok) throw new Error(await r.text());
    if (navigator.vibrate) navigator.vibrate(15);
    if (mode === "play") {
      uiToggleSearch(); // on referme : la musique a changé
    } else {
      // on reste dans la recherche, avec une coche en confirmation
      btn.innerHTML = '<i class="fa-solid fa-check"></i>';
      btn.disabled = true;
    }
  } catch (e) {
    alert("Erreur : " + e.message);
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

  if (window.currentRadio) {
    el.textContent = window.currentRadio.name;
    return;
  }

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
    if (!window.currentRadio && current && String(id) === String(current)) btn.classList.add("selected");
    btn.addEventListener("click", () => uiSelectPlaylist(id));
    listEl.appendChild(btn);
  }

  // radios en direct (si mpv est installé côté serveur)
  const radios = window.radios || [];
  if (radios.length) {
    const head = document.createElement("div");
    head.className = "plist-head";
    head.innerHTML = '<i class="fa-solid fa-tower-broadcast"></i> Radios en direct';
    listEl.appendChild(head);
    for (const radio of radios) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = radio.name;
      if (window.currentRadio && window.currentRadio.id === radio.id) btn.classList.add("selected");
      btn.addEventListener("click", () => uiSelectRadio(radio.id));
      listEl.appendChild(btn);
    }
  }
}

async function uiSelectRadio(id) {
  try {
    const r = await fetch("/api/radio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!r.ok) throw new Error(await r.text());
    if (navigator.vibrate) navigator.vibrate(15);
    uiTogglePlaylists(); // fermer
    await refresh();
  } catch (e) {
    alert("Impossible de lancer la radio : " + e.message);
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

(function () {
  const overlay = document.getElementById("plOverlay");
  if (!overlay) return;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) uiTogglePlaylists();
  });
})();

(function () {
  const overlay = document.getElementById("sOverlay");
  if (!overlay) return;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) uiToggleSearch();
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
