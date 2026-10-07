// REEL template: a 20 s product / studio reel at 120 BPM (1 beat = 0.5 s, 1 bar = 2 s).
// Story: hook -> pitch -> product UI assembles -> 3 features in one morphing
// container -> one number -> logo lockup + CTA.
//
// Rules (see CLAUDE.md / SKILL.md): pure function of time, springs only,
// no Math.random / Date / timers, draw in virtual units (S.W x S.H; the short
// side is always 1080). Edit COPY first; then timings; then visuals.
(function () {
  const { sp, track, range, clamp, lerp, ease, mixHex, rgba, swapAlpha } = M;

  const COPY = {
    hook: ['Launches', 'deserve', 'motion.'],
    pitch: 'We turn products into',
    slot: ['launch films.', 'product reels.', 'motion ads.'],
    ui: { title: 'Projects', button: 'Export', toast: 'Film exported', kpis: [['Films', '128'], ['Formats', '3'], ['Avg. length', '24s']] },
    features: [
      { k: '01', title: 'Kinetic type', sub: 'Every word on a spring' },
      { k: '02', title: 'Sound on the beat', sub: 'Score and SFX made in code' },
      { k: '03', title: 'Every format', sub: 'One timeline, three crops' },
    ],
    // PLACEHOLDER claim. Replace with a real, provable number before publishing.
    metric: { value: 48, suffix: 'h', label: 'from brief to final cut' },
  };

  // Beat-grid timings (seconds). Everything lands on a beat.
  const T = { pitch: 2.0, ui: 3.75, feat: 8.0, metric: 14.0, lock: 16.0, end: 20.0 };

  let C, BR;
  const L = {};   // layout, computed once per format in setup()

  function setup(S) {
    BR = S.BRAND; C = BR.colors;
    const { W, H } = S, wide = S.fmt === 'wide', tall = S.fmt === 'tall';
    L.wide = wide; L.tall = tall;
    L.m = wide ? 150 : 90;                                     // side margin
    L.hook = wide ? 260 : Math.min(200, W * 0.165);
    L.card = wide ? { x: W / 2 - 600, y: H / 2 - 350, w: 1200, h: 700 }
      : tall ? { x: 70, y: H / 2 - 520, w: W - 140, h: 1040 }
      : { x: 90, y: 150, w: W - 180, h: H - 300 };
    // Feature container states
    const fx = wide ? W * 0.53 : 90, fw = wide ? W * 0.39 : W - 180;
    const fy = wide ? H * 0.2 : tall ? H * 0.42 : H * 0.46, fh = wide ? H * 0.6 : tall ? H * 0.42 : H * 0.44;
    L.f1 = { x: fx, y: fy, w: fw, h: fh, r: 44 };
    L.f2 = { x: fx - (wide ? 40 : 0), y: fy + fh * 0.25, w: fw + (wide ? 40 : 0), h: fh * 0.5, r: fh * 0.25 };
    const ccx = fx + fw / 2, ccy = fy + fh / 2;
    const ratio = (rw, rh) => { const s = Math.min(fw / rw, fh / rh) * 0.95; return { x: ccx - rw * s / 2, y: ccy - rh * s / 2, w: rw * s, h: rh * s, r: 28 }; };
    L.f3 = [ratio(16, 9), ratio(1, 1), ratio(9, 16), ratio(16, 9)];
    L.full = { x: 0, y: 0, w: W, h: H, r: 0 };
    L.textX = L.m; L.textY = wide ? H * 0.42 : tall ? H * 0.16 : H * 0.22;
  }

  // ---------------------------------------------------------------- helpers
  const bgFill = (S, col) => { S.g.fillStyle = col; S.g.fillRect(0, 0, S.W, S.H); };

  function dotGrid(S, col, t) {
    const { g, W, H } = S, gap = 54, drift = (t * 6) % gap;
    g.fillStyle = rgba(col, 0.07);
    for (let y = -gap + drift; y < H + gap; y += gap) for (let x = 0; x < W + gap; x += gap) g.fillRect(x, y, 3, 3);
  }

  // Accent panel wipe: covers bottom-up over [t0, tm], uncovers upward over [tm, t1].
  function wipe(S, t, t0, tm, t1, col) {
    if (t < t0 || t > t1) return;
    const { g, W, H } = S;
    const top = H * (1 - ease.inOutCubic(range(t, t0, tm)));
    const bottom = H * (1 - ease.inOutCubic(range(t, tm, t1)));
    g.fillStyle = col; g.fillRect(0, top, W, bottom - top);
  }

  function rectAt(t, keys, preset) {   // keys: [[time, {x,y,w,h,r}], ...]
    return M.trackObj(t, keys, preset);
  }

  // ---------------------------------------------------------------- scenes
  const hook = {
    name: 'hook', from: 0, to: 2.0, draw(S, lt) {
      const { g, W, H } = S;
      bgFill(S, C.bg);
      const size = L.hook, lh = size * 0.98;
      const y0 = (H - 3 * lh) / 2 + size * 0.8;
      COPY.hook.forEach((w, i) => {
        D.words(g, w, L.m, y0 + i * lh, lt - i * 0.5, {
          role: 'display', weight: 700, size, color: i === 2 ? C.accent : C.inkOnDark, preset: 'heavy',
          out: 1.62 - i * 0.5 + i * 0.04, track: -0.035,
        });
      });
      // underline grows on beat 3
      const p = sp(lt - 1.5, 'snap'), q = sp(lt - 1.72, 'snap');
      const uw = D.measure(g, COPY.hook[2], { role: 'display', weight: 700, size, track: -0.035 });
      g.fillStyle = C.accent; g.fillRect(L.m + uw * q, y0 + 2 * lh + size * 0.16, uw * (p - q), size * 0.07);
    },
  };

  const pitch = {
    name: 'pitch', from: T.pitch, to: T.ui + 0.25, draw(S, lt) {
      const { g, W, H } = S;
      bgFill(S, C.paper); dotGrid(S, C.ink, S.t);
      const size = L.wide ? 96 : 76, big = L.wide ? 210 : L.hook * 0.78;
      const y = L.wide ? H * 0.4 : H * 0.36;
      D.words(g, COPY.pitch, L.m, y, lt - 0.2, { role: 'ui', weight: 600, size, color: C.ink, stagger: 0.05, preset: 'ui', out: 1.65, maxW: S.W - L.m * 2 });
      // slot machine: one word per beat, rolling up on a spring
      const lh = big * 1.08, sy = y + (L.wide ? size * 0.9 : size * 2.2) + big * 0.9;
      const roll = track(lt, [[0, 0], [0.5, 1], [1.0, 2]], 'ui');
      const enter = sp(lt - 0.25, 'heavy'), leave = sp(lt - 1.7, 'snap');
      g.save(); g.beginPath(); g.rect(0, sy - big * 0.95, W, big * 1.25); g.clip();
      COPY.slot.forEach((w, i) => {
        const yy = sy + (i - roll) * lh + (1 - enter) * lh - leave * lh * 1.2;
        D.text(g, w, L.m, yy, { role: 'display', weight: 700, size: big, color: C.accent, track: -0.03,
          alpha: Math.abs(i - roll) < 0.6 ? 1 : 0 });
      });
      g.restore();
    },
  };

  // Product UI assembles. If assets/screen.(png|jpg) exists, the real
  // screenshot is used inside the window instead of the drawn mock.
  const ui = {
    name: 'ui', from: T.ui, to: T.feat + 0.05, draw(S, lt) {
      const { g, W, H, A } = S, k = L.card;
      bgFill(S, C.paper); dotGrid(S, C.ink, S.t);
      const dur = T.feat - T.ui;
      const inP = sp(lt - 0.05, 'base');
      const content = swapAlpha(lt, 0.1, dur - 0.05);        // content leaves before the morph
      const cam = 1 + 0.03 * Math.sin(Math.PI * clamp(lt / dur));
      g.translate(W / 2, H / 2); g.scale(cam, cam); g.translate(-W / 2, -H / 2);
      g.translate(0, (1 - inP) * 220);
      const s = lerp(0.82, 1, inP);
      g.translate(k.x + k.w / 2, k.y + k.h / 2); g.scale(s, s); g.translate(-(k.x + k.w / 2), -(k.y + k.h / 2));
      // window
      g.save(); g.shadowColor = 'rgba(0,0,0,0.18)'; g.shadowBlur = 60; g.shadowOffsetY = 24;
      D.box(g, k.x, k.y, k.w, k.h, 28, '#FFFFFF'); g.restore();
      g.save(); D.rr(g, k.x, k.y, k.w, k.h, 28); g.clip();
      g.globalAlpha = content;
      const bar = 64;
      g.fillStyle = '#F4F3EF'; g.fillRect(k.x, k.y, k.w, bar);
      ['#FF5F57', '#FEBC2E', '#28C840'].forEach((c, i) => { g.fillStyle = c; g.beginPath(); g.arc(k.x + 34 + i * 26, k.y + bar / 2, 8, 0, 7); g.fill(); });
      D.text(g, COPY.ui.title, k.x + 130, k.y + bar / 2 + 9, { role: 'ui', weight: 600, size: 26, color: C.ink });
      // export button (cursor clicks it)
      const bw = 170, bh = 44, bx = k.x + k.w - bw - 24, by = k.y + (bar - bh) / 2;
      const tClick = 2.85, press = sp(lt - tClick, 'snap') - sp(lt - tClick - 0.12, 'snap');
      const filled = sp(lt - tClick - 0.05, 'ui');
      D.box(g, bx, by + press * 3, bw, bh, 12, mixHex(C.ink, C.accent, filled));
      D.text(g, COPY.ui.button, bx + bw / 2, by + bh / 2 + 9 + press * 3, { role: 'ui', weight: 600, size: 22, color: '#fff', align: 'center' });
      const cy0 = k.y + bar, ch = k.h - bar;
      if (A.screen) {
        const p = sp(lt - 0.35, 'base');
        D.image(g, A.screen, k.x, cy0 + (1 - p) * 40, k.w, ch, 0);
      } else {
        // sidebar slides in
        const sw = k.w * (L.tall ? 0 : 0.2), sp1 = sp(lt - 0.35, 'ui');
        if (sw) {
          g.fillStyle = C.ink; g.fillRect(k.x - sw * (1 - sp1), cy0, sw, ch);
          for (let i = 0; i < 5; i++) {
            const pi = sp(lt - 0.5 - i * 0.06, 'ui');
            D.box(g, k.x + 28 - (1 - pi) * 60, cy0 + 40 + i * 58, sw * (i === 0 ? 0.7 : 0.55), 18, 9, i === 0 ? C.accent : rgba('#FFFFFF', 0.18));
          }
        }
        const cx = k.x + sw + 40, cw = k.w - sw - 80;
        // KPI tiles pop on beats
        const tw = (cw - 40) / 3, th = L.tall ? 170 : 130;
        COPY.ui.kpis.forEach(([lab, val], i) => {
          const p = sp(lt - 0.5 - i * 0.25, 'ui');
          const x = cx + i * (tw + 20), y = cy0 + 36;
          g.save(); g.translate(x + tw / 2, y + th / 2); g.scale(lerp(0.6, 1, p), lerp(0.6, 1, p)); g.globalAlpha *= clamp(p * 3);
          D.box(g, -tw / 2, -th / 2, tw, th, 18, '#F6F5F1');
          D.text(g, lab, -tw / 2 + 24, -th / 2 + 42, { role: 'ui', weight: 400, size: 22, color: C.muted });
          D.text(g, val, -tw / 2 + 24, th / 2 - 28, { role: 'display', weight: 700, size: L.tall ? 70 : 56, color: C.ink });
          g.restore();
        });
        // bar chart grows, staggered
        const gy = cy0 + 36 + th + 40, gh = ch - th - 36 - 40 - 50;
        D.box(g, cx, gy, cw, gh, 18, '#F6F5F1');
        const n = 12, bwid = (cw - 80) / n;
        const r = M.rng(5);
        for (let i = 0; i < n; i++) {
          const v = 0.25 + 0.7 * (0.5 + 0.5 * Math.sin(i * 0.9 + 1)) * (0.7 + 0.3 * r());
          const p = sp(lt - 1.0 - i * 0.045, 'ui');
          const hgt = (gh - 70) * v * p;
          D.box(g, cx + 40 + i * bwid + bwid * 0.18, gy + gh - 30 - hgt, bwid * 0.64, hgt, 8, i === 9 ? C.accent : C.ink);
        }
      }
      g.restore();
      // cursor travels to the button and clicks
      const cur = M.trackObj(lt, [[0, { x: k.x + k.w * 0.75, y: k.y + k.h + 260 }], [2.2, { x: bx + bw * 0.55, y: by + bh * 0.6 }]], 'base');
      if (lt > 1.9 && content > 0.01) {
        g.save(); g.globalAlpha = content;
        D.ripple(g, bx + bw * 0.55, by + bh * 0.6, lt, tClick, C.accent);
        D.cursor(g, cur.x, cur.y, press, 1.4); g.restore();
      }
      // toast
      const tp = sp(lt - 3.15, 'ui') - sp(lt - (dur - 0.35), 'snap');
      if (tp > 0.001) {
        const tw2 = 420, th2 = 76, tx = k.x + k.w / 2 - tw2 / 2, ty = k.y + k.h - 40 - th2 + (1 - tp) * 140;
        g.save(); g.globalAlpha = clamp(tp * 2);
        D.box(g, tx, ty, tw2, th2, 38, C.ink);
        g.fillStyle = C.accent; g.beginPath(); g.arc(tx + 40, ty + th2 / 2, 14, 0, 7); g.fill();
        D.text(g, COPY.ui.toast, tx + 72, ty + th2 / 2 + 10, { role: 'ui', weight: 600, size: 28, color: C.inkOnDark });
        g.restore();
      }
    },
  };

  // Three features inside ONE container that never cuts. It starts at the
  // UI window's rect, morphs per feature, then expands to fill the screen.
  const feats = {
    name: 'features', from: T.feat, to: T.metric + 0.1, draw(S, lt) {
      const { g, W, H } = S;
      bgFill(S, C.paper); dotGrid(S, C.ink, S.t);
      const k = { ...L.card, r: 28 };
      const keys = [[0, k], [0.12, L.f1], [2.0, L.f2], [4.0, L.f3[0]], [4.5, L.f3[1]], [5.0, L.f3[2]], [5.5, L.f3[3]], [5.85, L.full]];
      const R = rectAt(lt, keys, 'ui');
      const fills = [['#FFFFFF', 0], [C.ink, 0.12], [C.accent, 2.0], [C.ink, 4.0]];
      let fill = fills[0][0];
      for (let i = 1; i < fills.length; i++) fill = mixHex(fill, fills[i][0], sp(lt - fills[i][1], 'base'));
      D.box(g, R.x, R.y, R.w, R.h, R.r, fill);

      // left / top text column, swaps per feature
      COPY.features.forEach((f, i) => {
        const t0 = i * 2 + 0.15, out = i < 2 ? 1.62 : 1.45;
        if (lt < t0 - 0.05 || lt > t0 + 2.2) return;
        const lx = L.textX, ly = L.textY, ts = L.wide ? 118 : 104;
        D.words(g, f.k, lx, ly - ts * 0.9, lt - t0, { role: 'display', weight: 500, size: 44, color: C.accent, out, preset: 'ui' });
        D.words(g, f.title, lx, ly + 20, lt - t0 - 0.06, { role: 'display', weight: 700, size: ts, color: C.ink, out, track: -0.03, maxW: L.wide ? W * 0.42 : W - L.m * 2, stagger: 0.06 });
        const lines = D.wrap(g, f.title, L.wide ? W * 0.42 : W - L.m * 2, { role: 'display', weight: 700, size: ts, track: -0.03 }).length;
        D.words(g, f.sub, lx, ly + 20 + lines * ts * 1.02 + 30, lt - t0 - 0.18, { role: 'ui', weight: 400, size: 46, color: C.muted, out, preset: 'ui', stagger: 0.04 });
      });

      g.save(); D.rr(g, R.x, R.y, R.w, R.h, R.r); g.clip();
      const cx = R.x + R.w / 2, cy = R.y + R.h / 2;
      // F1: letters bounce on every beat
      const a1 = swapAlpha(lt, 0.15, 2.0);
      if (a1 > 0) {
        g.globalAlpha = a1;
        const word = 'MOTION', size = Math.min(R.w / 4.4, 190), ww = D.measure(g, word, { role: 'display', weight: 700, size });
        let x = cx - ww / 2;
        for (let i = 0; i < word.length; i++) {
          const ch = word[i], cw = D.measure(g, ch, { role: 'display', weight: 700, size });
          const hit = Math.max(0, ...[0.5, 1.0, 1.5].map((b) => b + i * 0.04 <= lt ? Math.exp(-(lt - b - i * 0.04) * 7) : 0));
          const p = sp(lt - 0.25 - i * 0.05, 'play');
          g.save(); g.translate(x + cw / 2, cy + size * 0.35 - hit * 40);
          g.scale(p * (1 + hit * 0.12), p * (1 - hit * 0.08));
          D.text(g, ch, 0, 0, { role: 'display', weight: 700, size, color: i === 2 ? C.accent : C.inkOnDark, align: 'center' });
          g.restore(); x += cw;
        }
        g.globalAlpha = 1;
      }
      // F2: waveform bars driven by the beat grid
      const a2 = swapAlpha(lt, 2.0, 4.0);
      if (a2 > 0) {
        g.globalAlpha = a2;
        const n = 28, gap = R.w * 0.7 / n, abs = S.t;
        const spb = S.B.spb, since = ((abs % spb) + spb) % spb;
        const kick = Math.exp(-since * 9);
        for (let i = 0; i < n; i++) {
          const env = Math.sin(Math.PI * (i + 0.5) / n);
          const wob = 0.35 + 0.65 * Math.abs(M.noise1(abs * 3 + i * 0.7, 3));
          const h = R.h * 0.62 * env * (0.25 + 0.75 * wob * (0.45 + 0.55 * kick)) * sp(lt - 2.15 - i * 0.012, 'ui');
          D.box(g, cx - R.w * 0.35 + i * gap + gap * 0.2, cy - h / 2, gap * 0.6, h, gap * 0.3, C.ink);
        }
        g.globalAlpha = 1;
      }
      // F3: the container itself is the demo; label its ratio
      const ratios = ['16:9', '1:1', '9:16', '16:9'];
      ratios.forEach((r, i) => {
        const a = swapAlpha(lt, 4.0 + i * 0.5, i < 3 ? 4.5 + i * 0.5 : 5.75);
        if (a <= 0) return;
        D.text(g, r, cx, cy + 26, { role: 'display', weight: 700, size: Math.min(R.w, R.h) * 0.26, color: C.inkOnDark, align: 'center', alpha: a });
      });
      g.restore();
    },
  };

  const metric = {
    name: 'metric', from: T.metric, to: T.lock + 0.4, draw(S, lt) {
      const { g, W, H } = S;
      bgFill(S, C.ink);
      const m = COPY.metric, size = L.wide ? 420 : 330;
      const p = ease.outExpo(range(lt, 0.15, 1.25));
      const leave = sp(lt - 1.75, 'snap');
      const str = D.num(Math.round(m.value * p)) + m.suffix;
      const y = H / 2 + size * 0.28 - leave * H * 0.6;
      const enter = sp(lt - 0.05, 'heavy');
      g.save(); g.translate(W / 2, y); g.scale(lerp(0.85, 1, enter), lerp(0.85, 1, enter));
      D.text(g, str, 0, 0, { role: 'display', weight: 700, size, color: C.accent, align: 'center', track: -0.04, alpha: clamp(enter * 4) });
      g.restore();
      D.words(g, m.label, W / 2, y + size * 0.32, lt - 0.45, { role: 'ui', weight: 600, size: 52, color: C.inkOnDark, align: 'center', out: 1.65, preset: 'ui' });
      // circle reveal into the lockup
      const rp = ease.inOutCubic(range(lt, 1.75, 2.15));
      if (rp > 0) { g.fillStyle = C.paper; g.beginPath(); g.arc(W / 2, H / 2, Math.hypot(W, H) / 2 * rp, 0, 7); g.fill(); }
    },
  };

  const lockup = {
    name: 'lockup', from: T.lock + 0.15, to: T.end + 0.01, draw(S, lt0) {
      const { g, W, H, A } = S, lt = lt0 + 0.15;      // lt = time since T.lock
      bgFill(S, C.paper); dotGrid(S, C.ink, S.t);
      const markS = L.wide ? 190 : 170, nameS = L.wide ? 220 : 150;
      const cy = H / 2 - (L.wide ? 60 : 120);
      const pm = sp(lt - 0.15, 'heavy');
      // Real logo if present (drawn alone: most logos already contain the name),
      // else a geometric mark + the brand name.
      if (A.logo) {
        const r = A.logo.width / A.logo.height, h = Math.min(markS * 1.3, (W * 0.5) / r), w = h * r;
        g.save(); g.translate(W / 2, cy); g.scale(pm, pm); g.drawImage(A.logo, -w / 2, -h / 2, w, h); g.restore();
      } else {
        const nameW = D.measure(g, BR.name, { role: 'display', weight: 700, size: nameS, track: -0.04 });
        const gap = markS * 0.3 + 40, total = markS + gap + nameW, x0 = W / 2 - total / 2;
        g.save(); g.translate(x0 + markS / 2, cy); g.scale(pm, pm);
        g.rotate((Math.PI / 4) * sp(lt - 0.5, 'base'));
        D.box(g, -markS / 2, -markS / 2, markS, markS, 26 * pm, C.accent);
        g.rotate(-(Math.PI / 4) * sp(lt - 0.5, 'base'));
        const dp = sp(lt - 0.75, 'play');
        g.fillStyle = C.paper; g.beginPath(); g.arc(0, 0, markS * 0.17 * dp, 0, 7); g.fill();
        g.restore();
        D.words(g, BR.name, x0 + markS + gap, cy + nameS * 0.36, lt - 0.45, { role: 'display', weight: 700, size: nameS, color: C.ink, track: -0.04 });
      }
      D.words(g, BR.tagline, W / 2, cy + markS * 0.5 + 110, lt - 0.85, { role: 'ui', weight: 400, size: L.wide ? 44 : 40, color: C.muted, align: 'center', stagger: 0.035, preset: 'ui', maxW: W - L.m * 2 });
      // CTA button pops, cursor clicks it
      const bw = Math.max(380, D.measure(g, BR.cta, { role: 'ui', weight: 600, size: 40 }) + 120), bh = 96;
      const bx = W / 2 - bw / 2, by = cy + markS * 0.5 + 180;
      const bp = sp(lt - 1.4, 'ui'), tc = 2.6;
      const press = sp(lt - tc, 'snap') - sp(lt - tc - 0.12, 'snap');
      if (bp > 0.001) {
        g.save(); g.translate(W / 2, by + bh / 2); const s = bp * (1 - press * 0.05); g.scale(s, s);
        D.box(g, -bw / 2, -bh / 2, bw, bh, bh / 2, mixHex(C.ink, C.accent, sp(lt - tc - 0.04, 'ui')));
        D.text(g, BR.cta, 0, 14, { role: 'ui', weight: 600, size: 40, color: '#fff', align: 'center' });
        g.restore();
      }
      D.ripple(g, W / 2 + 40, by + bh / 2 + 10, lt, tc, C.accent, 70);
      if (lt > 1.7) {
        const cur = M.trackObj(lt, [[0, { x: W * 0.85, y: H + 200 }], [1.9, { x: W / 2 + 40, y: by + bh / 2 + 10 }]], 'base');
        D.cursor(g, cur.x, cur.y, press, 1.5);
      }
      if (BR.url) D.words(g, BR.url, W / 2, by + bh + 80, lt - 2.8, { role: 'ui', weight: 600, size: 34, color: C.ink, align: 'center', preset: 'ui' });
    },
  };

  window.FILM = {
    duration: T.end, bpm: 120, loop: false,
    bg: '#121211',
    setup,
    scenes: [hook, pitch, ui, feats, metric, lockup],
    overlay(S, t) {
      wipe(S, t, 1.72, 2.0, 2.3, C.accent);          // hook -> pitch
    },
    // SFX on the timeline. Types: click tick type pop thump impact whoosh swish rise success
    cues(B) {
      const c = [];
      [0, 0.5, 1.0].forEach((t) => c.push({ t, type: 'thump', gain: 0.8 }));
      c.push({ t: 1.5, type: 'swish' }, { t: 2.0, type: 'whoosh' });
      [2.5, 3.0, 3.5].forEach((t) => c.push({ t, type: 'tick', gain: 0.8 }));
      c.push({ t: T.ui + 0.1, type: 'whoosh', gain: 0.7 });
      [0.5, 0.75, 1.0].forEach((d) => c.push({ t: T.ui + d, type: 'pop', gain: 0.6 }));
      c.push({ t: T.ui + 2.85, type: 'click' }, { t: T.ui + 3.15, type: 'success', gain: 0.8 });
      c.push({ t: T.feat, type: 'whoosh', gain: 0.8 });
      [0.5, 1.0, 1.5].forEach((d) => c.push({ t: T.feat + d, type: 'pop', gain: 0.5 }));
      c.push({ t: T.feat + 2.0, type: 'swish' });
      [4.0, 4.5, 5.0, 5.5].forEach((d) => c.push({ t: T.feat + d, type: 'swish', gain: 0.7 }));
      c.push({ t: T.metric - 0.1, type: 'rise', gain: 0.4 }, { t: T.metric, type: 'impact', gain: 0.7 });
      for (let i = 0; i < 8; i++) c.push({ t: T.metric + 0.15 + ease.outExpo(i / 8) * 1.0, type: 'tick', gain: 0.5 });
      c.push({ t: T.lock + 0.15, type: 'impact' }, { t: T.lock + 1.4, type: 'pop' });
      c.push({ t: T.lock + 2.6, type: 'click' }, { t: T.lock + 2.65, type: 'success' });
      return c;
    },
  };
})();
