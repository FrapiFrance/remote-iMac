
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

    // FIXME : wip
    document.getElementById('playlist').textContent = s.playlist_id || "—";


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


function uiOpenQueue() {
  // Placeholder: you said “later for implementation”.
  // For now, you can hook a bottom-sheet here.
  alert("Queue: à implémenter (bottom sheet)");
}

function uiOpenPlaylists() {
  // Placeholder: you said “later for implementation”.
  // For now, you can hook a bottom-sheet here.
  alert("Playlists: à implémenter (bottom sheet)");
}

refresh();
setInterval(refresh, 1500);
