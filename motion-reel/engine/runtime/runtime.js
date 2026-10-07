// Runtime: loads fonts + assets, exposes window.seek(t) and window.frame(t).
// The film (film.js) sets window.FILM = { duration, bpm, scenes, cues, ... }.
(function () {
  'use strict';
  const C = window.CFG, W = C.W, H = C.H;
  const out = document.getElementById('c'); out.width = W; out.height = H;
  const octx = out.getContext('2d');
  const work = document.createElement('canvas'); work.width = W; work.height = H;
  const g = work.getContext('2d');

  // Beat grid. Films are always authored on a steady FILM.bpm grid ("film
  // time"). When a real track was measured (beats.json, measured: true), real
  // time is warped beat-by-beat onto film time, so every cut written for
  // 120 BPM lands on the track's actual beats, whatever its tempo or drift.
  function makeBeats() {
    const bpm = window.FILM.bpm || 120, spb = 60 / bpm;
    const beat = (n) => n * spb;
    return { bpm, spb, beat, bar: (n) => beat(n * 4) };
  }
  const RB = (C.beats && C.beats.measured && C.beats.beats.length > 4) ? C.beats.beats : null;
  function warp(t) {                     // real seconds -> film seconds
    if (!RB) return t;
    const spb0 = 60 / (window.FILM.bpm || 120), n = RB.length;
    let b;
    if (t <= RB[0]) b = (t - RB[0]) / (RB[1] - RB[0]);
    else if (t >= RB[n - 1]) b = n - 1 + (t - RB[n - 1]) / (RB[n - 1] - RB[n - 2]);
    else { let i = 0; while (RB[i + 1] < t) i++; b = i + (t - RB[i]) / (RB[i + 1] - RB[i]); }
    return b * spb0;
  }
  function unwarp(ft) {                  // film seconds -> real seconds
    if (!RB) return ft;
    const spb0 = 60 / (window.FILM.bpm || 120), b = ft / spb0, n = RB.length;
    if (b <= 0) return RB[0] + b * (RB[1] - RB[0]);
    if (b >= n - 1) return RB[n - 1] + (b - n + 1) * (RB[n - 1] - RB[n - 2]);
    const i = Math.floor(b); return RB[i] + (b - i) * (RB[i + 1] - RB[i]);
  }

  const A = {};            // loaded images by name
  let B, S;

  // Films draw in a virtual space where the short side is always 1080 units
  // (16:9 = 1920x1080, 9:16 = 1080x1920), whatever the output resolution.
  const U = Math.min(W, H) / 1080;
  function context(t) { S.t = t; return S; }

  function paint(t) {
    const F = window.FILM;
    window.__boxes = [];
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
    g.fillStyle = F.bg || BRAND.colors.bg; g.fillRect(0, 0, W, H);
    g.setTransform(U, 0, 0, U, 0, 0);
    const s = context(t);
    if (F.background) { g.save(); F.background(s, t); g.restore(); }
    for (const sc of F.scenes) {
      if (t >= sc.from && t < sc.to) {
        g.save(); sc.draw(s, t - sc.from, sc.to - sc.from); g.restore();
      }
    }
    if (F.overlay) { g.save(); F.overlay(s, t); g.restore(); }
    g.setTransform(1, 0, 0, 1, 0, 0);
    if (F.grain !== false) D.grain(g, W, H, t, C.fps, F.grain || 0.045);
    if (C.debug) {
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.fillStyle = 'rgba(0,0,0,.7)'; g.fillRect(0, 0, 210 * (W / 1920) + 60, 64);
      g.fillStyle = '#ff0'; g.font = `600 ${Math.round(40 * Math.max(1, W / 1920))}px monospace`;
      g.fillText(lastReal.toFixed(2) + 's', 14, 46);
    }
  }

  // Single frame, no blur. Used for previews and stills.
  let lastReal = 0;
  window.seek = (t) => { lastReal = t; paint(warp(t)); octx.globalAlpha = 1; octx.drawImage(work, 0, 0); return true; };

  // Render frame with sub-frame motion blur (shutter = fraction of a frame).
  // Running average: subframe k drawn with alpha 1/(k+1).
  window.frame = (t, sub = 1, shutter = 0.5, type = 'image/png', q = 0.95) => {
    lastReal = t;
    if (sub <= 1) window.seek(t);
    else {
      for (let k = 0; k < sub; k++) {
        paint(warp(t + ((k + 0.5) / sub - 0.5) * (shutter / C.fps)));
        octx.globalAlpha = 1 / (k + 1); octx.drawImage(work, 0, 0);
      }
      octx.globalAlpha = 1;
    }
    return out.toDataURL(type, q);
  };

  window.boxes = () => window.__boxes.slice();

  window.meta = () => {
    const F = window.FILM;
    const cues = typeof F.cues === 'function' ? F.cues(B) : (F.cues || []);
    // Everything returned here is in real (audio) seconds.
    return { duration: unwarp(F.duration), bpm: B.bpm, warped: !!RB, loop: !!F.loop,
      cues: cues.map((c) => Object.assign({}, c, { t: unwarp(c.t) })),
      scenes: F.scenes.map((s) => [unwarp(s.from), unwarp(s.to), s.name || '']) };
  };

  async function boot() {
    const fails = [];
    for (const role of Object.keys(BRAND.fonts)) {
      const f = BRAND.fonts[role];
      for (const w of Object.keys(f.files)) {
        try { await document.fonts.load(`${w} 40px "${f.family}"`); } catch (e) { fails.push(f.family + ' ' + w); }
        if (!document.fonts.check(`${w} 40px "${f.family}"`)) fails.push(f.family + ' ' + w);
      }
    }
    await Promise.all(Object.entries(C.assets || {}).map(([name, url]) => new Promise((res) => {
      const im = new Image(); im.onload = () => { A[name] = im; res(); };
      im.onerror = () => { fails.push('asset ' + name); res(); }; im.src = url;
    })));
    B = makeBeats();
    const VW = W / U, VH = H / U;
    S = { g, W: VW, H: VH, u: U, B, A, C, BRAND, cx: VW / 2, cy: VH / 2, fmt: W > H ? 'wide' : W < H ? 'tall' : 'square' };
    if (window.FILM.setup) window.FILM.setup(S);
    window.__fails = fails;
    window.__ready = true;
  }
  window.__boot = boot().catch((e) => { window.__error = String(e && e.stack || e); });

  // Live preview when opened in a normal browser.
  if (!navigator.webdriver) {
    window.__boot.then(() => {
      const t0 = performance.now();
      (function loop() { window.seek(((performance.now() - t0) / 1000) % window.FILM.duration); requestAnimationFrame(loop); })();
    });
  }
})();
