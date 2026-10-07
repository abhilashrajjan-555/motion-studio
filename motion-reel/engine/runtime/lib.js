// Motion + drawing library. Everything here is a pure function of its inputs,
// so any frame can be rendered on its own (the seek(t) contract).
(function () {
  'use strict';

  // ---------- math ----------
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, p) => a + (b - a) * p;
  const range = (t, a, b) => clamp((t - a) / (b - a));          // 0..1 over [a,b]
  const loopT = (t, dur) => ((t % dur) + dur) % dur;

  // ---------- springs (closed form, mass = 1, 0 -> 1) ----------
  function spring(t, k = 170, d = 26) {
    if (t <= 0) return 0;
    const w0 = Math.sqrt(k), z = d / (2 * w0);
    if (z < 1) {
      const wd = w0 * Math.sqrt(1 - z * z);
      return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + (z * w0 / wd) * Math.sin(wd * t));
    }
    if (z === 1) return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
    const s = Math.sqrt(z * z - 1), r1 = -w0 * (z - s), r2 = -w0 * (z + s);
    return 1 - (r2 * Math.exp(r1 * t) - r1 * Math.exp(r2 * t)) / (r2 - r1);
  }

  // Presets. UI gets a hair of overshoot, type and logos get none.
  const P = {
    snap:  [400, 36],   // buttons, toggles, leading edges
    ui:    [300, 30],   // default UI, tiny overshoot
    base:  [170, 26],   // cards, containers, camera (critical)
    heavy: [100, 20],   // big type, logo lockups (critical, slower)
    play:  [260, 14],   // mascots, stickers (visible overshoot)
  };
  const sp = (t, preset = 'base') => { const [k, d] = P[preset] || preset; return spring(t, k, d); };

  // A value with several targets: one spring per change, summed. Never restarts.
  // keys: [[time, value], ...] sorted by time.
  function track(t, keys, preset = 'base') {
    let v = keys[0][1];
    for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * sp(t - keys[i][0], preset);
    return v;
  }
  // Same for points / objects of numbers: keys [[time, {x, y, w...}], ...]
  function trackObj(t, keys, preset = 'base') {
    const out = {};
    for (const f of Object.keys(keys[0][1])) out[f] = track(t, keys.map(([kt, o]) => [kt, o[f]]), preset);
    return out;
  }
  // Leading and trailing edges on different springs, so indicators stretch.
  function stretch(t, stops, size) {
    const lead = track(t, stops, 'snap'), trail = track(t, stops, 'base');
    return { a: Math.min(lead, trail), b: Math.max(lead, trail) + size };
  }
  // Text inside a morphing box: in after the morph starts, out before the next one.
  const swapAlpha = (t, tIn, tOut) => Math.min(clamp((t - tIn - 0.08) / 0.12), clamp((tOut - 0.1 - t) / 0.1));

  // Classic eases, only for things that are not physical (wipes, counters).
  const ease = {
    outExpo: (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
    inOutCubic: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    outCubic: (p) => 1 - Math.pow(1 - p, 3),
    inCubic: (p) => p * p * p,
  };

  // ---------- seeded randomness (never Math.random) ----------
  function rng(seed) {
    return () => {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const hash = (n, seed = 1) => rng((n * 374761393 + seed * 668265263) | 0)();
  function noise1(x, seed = 1) {                    // smooth value noise, -1..1
    const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
    return lerp(hash(i, seed), hash(i + 1, seed), u) * 2 - 1;
  }

  // ---------- color ----------
  function rgba(hex, a = 1) {
    const h = hex.replace('#', ''), n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  function mixHex(h1, h2, p) {
    const a = parseInt(h1.slice(1), 16), b = parseInt(h2.slice(1), 16);
    const c = [16, 8, 0].map((s) => Math.round(lerp((a >> s) & 255, (b >> s) & 255, clamp(p))));
    return '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');
  }

  window.M = { clamp, lerp, range, loopT, spring, P, sp, track, trackObj, stretch, swapAlpha, ease, rng, hash, noise1, rgba, mixHex };

  // ---------- drawing ----------
  // Every text draw records its on-screen box so `studio.py stills` can flag
  // text that leaves the safe area or overlaps other text.
  window.__boxes = [];
  function recordBox(g, str, x0, y0, x1, y1, alpha) {
    if (alpha < 0.3 || !str.trim()) return;
    const m = g.getTransform();
    const pts = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(([x, y]) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    window.__boxes.push({ str: str.slice(0, 40), x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) });
  }

  const D = {
    font(role, size, weight) {
      const f = (window.BRAND.fonts[role] || window.BRAND.fonts.ui);
      const w = weight || Object.keys(f.files).slice(-1)[0];
      return `${w} ${Math.round(size)}px "${f.family}", sans-serif`;
    },

    // text(g, str, x, y, {role, size, weight, color, align, base, track, alpha})
    text(g, str, x, y, o = {}) {
      const size = o.size || 48;
      g.save();
      g.font = D.font(o.role || 'ui', size, o.weight);
      g.letterSpacing = (o.track || 0) * size + 'px';
      g.textAlign = o.align || 'left';
      g.textBaseline = o.base || 'alphabetic';
      g.globalAlpha *= o.alpha == null ? 1 : o.alpha;
      g.fillStyle = o.color || '#fff';
      g.fillText(str, x, y);
      const m = g.measureText(str);
      recordBox(g, str, x - m.actualBoundingBoxLeft, y - m.actualBoundingBoxAscent,
        x + m.actualBoundingBoxRight, y + m.actualBoundingBoxDescent, g.globalAlpha);
      g.restore();
      return m.width;
    },

    measure(g, str, o = {}) {
      g.save(); g.font = D.font(o.role || 'ui', o.size || 48, o.weight);
      g.letterSpacing = (o.track || 0) * (o.size || 48) + 'px';
      const w = g.measureText(str).width; g.restore(); return w;
    },

    wrap(g, str, maxW, o = {}) {
      const words = str.split(' '), lines = []; let line = '';
      for (const w of words) {
        const test = line ? line + ' ' + w : w;
        if (line && D.measure(g, test, o) > maxW) { lines.push(line); line = w; } else line = test;
      }
      if (line) lines.push(line);
      return lines;
    },

    // Kinetic words: each word rises out of a mask on its own spring, then
    // leaves upward. No fades. o: {size, role, weight, color, stagger, preset,
    // maxW, lh (line height factor), out (local time to exit), align}
    words(g, str, x, y, lt, o = {}) {
      const size = o.size || 120, lh = size * (o.lh || 1.02), st = o.stagger == null ? 0.07 : o.stagger;
      const lines = o.maxW ? D.wrap(g, str, o.maxW, o) : [str];
      let idx = 0;
      lines.forEach((line, li) => {
        const ly = y + li * lh, lw = D.measure(g, line, o);
        let cx = o.align === 'center' ? x - lw / 2 : o.align === 'right' ? x - lw : x;
        g.save();
        g.beginPath(); g.rect(cx - size, ly - size * 1.0, lw + size * 2, size * 1.3); g.clip();
        for (const w of line.split(' ')) {
          const p = sp(lt - idx * st, o.preset || 'heavy');
          const q = o.out == null ? 0 : sp(lt - o.out - idx * st * 0.5, 'snap');
          const dy = (1 - p) * lh * 1.05 - q * lh * 1.1;
          const color = typeof o.color === 'function' ? o.color(w, idx) : o.color;
          D.text(g, w, cx, ly + dy, { ...o, color, alpha: p > 0.02 && q < 0.98 && Math.abs(dy) < lh * 0.9 ? 1 : 0, align: 'left' });
          cx += D.measure(g, w + ' ', o);
          idx++;
        }
        g.restore();
      });
      return { lines: lines.length, height: lines.length * lh };
    },

    // Rounded-rect path.
    rr(g, x, y, w, h, r) {
      r = Math.max(0, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2));
      g.beginPath(); g.roundRect(x, y, w, h, r);
    },
    box(g, x, y, w, h, r, fill, stroke, lw = 2) {
      D.rr(g, x, y, w, h, r);
      if (fill) { g.fillStyle = fill; g.fill(); }
      if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw; g.stroke(); }
    },

    // Draw an asset image with object-fit: cover inside a rounded box.
    image(g, img, x, y, w, h, r = 0, focus = [0.5, 0]) {
      if (!img) return false;
      const s = Math.max(w / img.width, h / img.height), iw = img.width * s, ih = img.height * s;
      g.save(); D.rr(g, x, y, w, h, r); g.clip();
      g.drawImage(img, x - (iw - w) * focus[0], y - (ih - h) * focus[1], iw, ih);
      g.restore(); return true;
    },

    // Arrow cursor. press 0..1 squashes it.
    cursor(g, x, y, press = 0, scale = 1) {
      g.save(); g.translate(x, y); const s = scale * (1 - 0.15 * press); g.scale(s, s);
      g.beginPath(); g.moveTo(0, 0); g.lineTo(0, 34); g.lineTo(9, 26); g.lineTo(15, 40);
      g.lineTo(21, 37); g.lineTo(15, 24); g.lineTo(27, 24); g.closePath();
      g.fillStyle = '#111'; g.fill(); g.strokeStyle = '#fff'; g.lineWidth = 2.5; g.stroke();
      g.restore();
    },

    // Click ring that expands from a point after time tc.
    ripple(g, x, y, t, tc, color, r = 46) {
      const p = range(t, tc, tc + 0.45); if (p <= 0 || p >= 1) return;
      g.save(); g.globalAlpha *= 1 - p; g.strokeStyle = color; g.lineWidth = 3;
      g.beginPath(); g.arc(x, y, r * ease.outCubic(p), 0, Math.PI * 2); g.stroke(); g.restore();
    },

    // Film grain from a fixed tile, stepped per frame (deterministic).
    grain(g, W, H, t, fps, amount = 0.05) {
      if (!D._grain) {
        const c = document.createElement('canvas'); c.width = c.height = 256;
        const x = c.getContext('2d'), id = x.createImageData(256, 256), r = rng(99);
        for (let i = 0; i < id.data.length; i += 4) { const v = r() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
        x.putImageData(id, 0, 0); D._grain = c;
      }
      const f = Math.floor(t * fps), r = rng(f + 7), ox = -r() * 256, oy = -r() * 256;
      g.save(); g.globalAlpha = amount; g.globalCompositeOperation = 'overlay';
      for (let y = oy; y < H; y += 256) for (let x = ox; x < W; x += 256) g.drawImage(D._grain, x, y);
      g.restore();
    },

    // Number formatting for counters.
    num(v, dec = 0) { return v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }); },
  };

  window.D = D;
})();
