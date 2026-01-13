
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
          const st = s.status || "Unknown";
          document.getElementById('state').textContent = (st === "Playing") ? "▶︎" : (st === "Paused") ? "⏸" : "…";
          if (typeof s.volume === "number") {
            document.getElementById('vol').value = s.volume;
            document.getElementById('volLabel').textContent = `${s.volume}%${s.muted ? " (muet)" : ""}`;
          }
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

      refresh();
      setInterval(refresh, 1500);
