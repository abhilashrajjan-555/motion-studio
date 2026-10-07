#!/usr/bin/env python3
"""motion-reel studio: code-rendered motion films.

  python3 studio.py setup                       install / check dependencies
  python3 studio.py new PROJECT [--brand studio] [--template reel]
  python3 studio.py capture URL PROJECT         real screenshots, colors, logo from a site
  python3 studio.py brand-from-site PROJECT SLUG   turn a capture into PROJECT/brand/
  python3 studio.py stills PROJECT [--every 0.5 | --at 1,2.5] [--format 16:9]
  python3 studio.py audio PROJECT               beats.json, music, sfx, mix (-14 LUFS)
  python3 studio.py render PROJECT [--format 16:9|9:16|1:1|all] [--draft] [--fps N] [--blur N]
  python3 studio.py qa PROJECT [--format 16:9]  contact sheet, strips, phone test, dead-time + determinism checks
  python3 studio.py all PROJECT                 audio -> render -> qa

A PROJECT folder holds: project.json, film.js, brief.md, assets/, audio/, out/.
"""
import argparse
import base64
import functools
import hashlib
import http.server
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
RUNTIME = HERE / 'runtime'
FORMATS = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350)}
IMG_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif'}
sys.path.insert(0, str(HERE))


# ------------------------------------------------------------------ helpers
def ffmpeg_bin():
    f = shutil.which('ffmpeg')
    if f:
        return f
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit('ffmpeg not found. Run: python3 studio.py setup')


def load_project(project):
    p = Path(project).resolve()
    cfg_path = p / 'project.json'
    if not cfg_path.exists():
        sys.exit(f'{cfg_path} not found. Create one with: python3 studio.py new {project}')
    cfg = json.loads(cfg_path.read_text())
    return p, cfg


def brand_dir(p, cfg):
    b = cfg.get('brand', 'studio')
    for cand in (p / 'brand', p / b, SKILL / 'brands' / b, Path(b)):
        if (cand / 'brand.json').exists():
            return cand.resolve()
    sys.exit(f'brand "{b}" not found (looked in PROJECT/brand, skill brands/{b})')


def fmt_list(cfg, arg):
    if arg == 'all':
        return cfg.get('formats', ['16:9'])
    return [arg or cfg.get('formats', ['16:9'])[0]]


class Server:
    """Serves the runtime, brand and project over http so canvas pixels stay
    readable (file:// images would taint the canvas)."""

    def __init__(self, roots):
        self.roots = {k: str(v) for k, v in roots.items()}
        roots_ = self.roots

        class H(http.server.SimpleHTTPRequestHandler):
            def translate_path(self, path):
                path = path.split('?')[0].lstrip('/')
                key, _, rest = path.partition('/')
                base = roots_.get(key)
                if not base:
                    return '/nonexistent'
                full = os.path.realpath(os.path.join(base, rest))
                return full if full.startswith(os.path.realpath(base)) else '/nonexistent'

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, key, rel=''):
        return f'http://127.0.0.1:{self.port}/{key}/{rel}'

    def close(self):
        self.httpd.shutdown()


def build_page(p, cfg, fmt, draft=False, debug=False, fps=30):
    """Write PROJECT/build/<fmt>.html and return (server, url)."""
    bdir = brand_dir(p, cfg)
    brand = json.loads((bdir / 'brand.json').read_text())
    W, H = FORMATS[fmt]
    if draft:
        W, H = W // 2, H // 2
    srv = Server({'engine': RUNTIME, 'brand': bdir, 'p': p})
    faces = []
    for role, f in brand['fonts'].items():
        for w, file in f['files'].items():
            faces.append(f"@font-face{{font-family:'{f['family']}';font-weight:{w};src:url('{srv.url('brand', file)}')}}")
    assets = {}
    adir = p / 'assets'
    if adir.exists():
        for a in sorted(adir.rglob('*')):
            if a.suffix.lower() in IMG_EXT:
                assets[a.stem] = srv.url('p', str(a.relative_to(p)))
    if brand.get('logo'):
        assets.setdefault('logo', srv.url('brand', brand['logo']))
    beats = None
    if (p / 'beats.json').exists():
        beats = json.loads((p / 'beats.json').read_text())
    C = {'W': W, 'H': H, 'fps': fps, 'assets': assets, 'beats': beats, 'debug': debug, 'format': fmt}
    html = f"""<!doctype html><html><head><meta charset="utf-8"><link rel="icon" href="data:,">
<style>{''.join(faces)} html,body{{margin:0;background:#000}} canvas{{display:block;max-width:100vw;max-height:100vh}}</style>
</head><body><canvas id="c"></canvas>
<script>window.CFG={json.dumps(C)};window.BRAND={json.dumps(brand)};</script>
<script src="{srv.url('engine', 'lib.js')}"></script>
<script src="{srv.url('p', 'film.js')}"></script>
<script src="{srv.url('engine', 'runtime.js')}"></script>
</body></html>"""
    (p / 'build').mkdir(exist_ok=True)
    name = fmt.replace(':', 'x') + ('_draft' if draft else '') + ('_debug' if debug else '') + '.html'
    (p / 'build' / name).write_text(html)
    return srv, srv.url('p', f'build/{name}'), (W, H)


def open_page(browser, url, size):
    page = browser.new_page(viewport={'width': size[0], 'height': size[1]}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.goto(url)
    page.wait_for_function('window.__ready === true || window.__error', timeout=60000)
    err = page.evaluate('window.__error')
    if err or errors:
        sys.exit('Film failed to load:\n' + (err or '') + '\n'.join(errors))
    fails = page.evaluate('window.__fails')
    if fails:
        print('WARNING: failed to load:', ', '.join(fails))
    return page


def launch(pw):
    try:
        return pw.chromium.launch()
    except Exception as e:
        # Playwright's pinned browser is missing: use any Chromium already on the machine.
        import glob
        pwb = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', os.path.expanduser('~/.cache/ms-playwright'))
        cands = [os.environ.get('CHROMIUM_PATH'), shutil.which('chromium'), shutil.which('chromium-browser'),
                 shutil.which('google-chrome'), *sorted(glob.glob(os.path.join(pwb, 'chromium-*/chrome-linux*/chrome')), reverse=True),
                 *sorted(glob.glob(os.path.join(pwb, 'chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium')), reverse=True)]
        for cand in cands:
            if cand and os.path.exists(cand):
                return pw.chromium.launch(executable_path=cand)
        raise SystemExit(f'Could not start Chromium ({e}). Run: python3 studio.py setup')


def get_meta(p, cfg, fmt=None):
    from playwright.sync_api import sync_playwright
    fmt = fmt or cfg.get('formats', ['16:9'])[0]
    srv, url, size = build_page(p, cfg, fmt, draft=True)
    with sync_playwright() as pw:
        b = launch(pw)
        meta = open_page(b, url, size).evaluate('window.meta()')
        b.close()
    srv.close()
    return meta


def data_url_bytes(d):
    return base64.b64decode(d.split(',', 1)[1])


# ------------------------------------------------------------------ setup / new
def cmd_setup(a):
    need = []
    for mod in ('playwright', 'numpy'):
        try:
            __import__(mod)
        except ImportError:
            need.append(mod)
    if need:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *need] +
                       (['--break-system-packages'] if sys.version_info >= (3, 11) else []), check=False)
    if not shutil.which('ffmpeg'):
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'imageio-ffmpeg'] +
                       (['--break-system-packages'] if sys.version_info >= (3, 11) else []), check=False)
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            launch(pw).close()
    except SystemExit:
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=False)
    try:
        import librosa  # noqa: F401
        lib = 'yes'
    except ImportError:
        lib = 'no (only needed to measure beats of a supplied track: pip install librosa)'
    ff = ffmpeg_bin()
    with sync_playwright() as pw:
        launch(pw).close()
    print(f'OK  ffmpeg: {ff}\nOK  chromium\nOK  numpy\n    librosa: {lib}')


def cmd_new(a):
    p = Path(a.project)
    if (p / 'film.js').exists() and not a.force:
        sys.exit(f'{p}/film.js already exists (use --force to overwrite)')
    tdir = SKILL / 'templates' / a.template
    if not tdir.exists():
        sys.exit(f'template "{a.template}" not found: ' + ', '.join(x.name for x in (SKILL / 'templates').iterdir()))
    for sub in ('assets', 'audio', 'out', 'docs', 'refs'):
        (p / sub).mkdir(parents=True, exist_ok=True)
    for f in tdir.iterdir():
        if f.is_file():
            shutil.copy(f, p / f.name)
    cfg = {
        'brand': a.brand, 'formats': ['16:9'], 'fps': 30, 'blur': 4,
        'music': {'source': 'synth', 'style': 'pulse', 'gain': 0.8},
        'sfx': {'gain': 0.9}, 'voice': {'source': 'none'}, 'loudness': -14,
    }
    if not (p / 'project.json').exists() or a.force:
        (p / 'project.json').write_text(json.dumps(cfg, indent=2))
    print(f'Created {p}/ (film.js, project.json, brief.md). Brand: {a.brand}. Template: {a.template}.')


# ------------------------------------------------------------------ capture
CAPTURE_JS = r"""() => {
  const css = (el, k) => getComputedStyle(el).getPropertyValue(k);
  const cnt = {}; const bump = (k, w) => { if (k && !/rgba\(0, 0, 0, 0\)|transparent/.test(k)) cnt[k] = (cnt[k] || 0) + w; };
  const els = [...document.querySelectorAll('body *')].slice(0, 4000);
  for (const el of els) { const r = el.getBoundingClientRect(); const area = Math.min(r.width * r.height, 2e5);
    if (area < 50) continue; bump(css(el, 'background-color'), area); bump(css(el, 'color'), 400); }
  const btn = [...document.querySelectorAll('a,button')].map(b => css(b, 'background-color')).filter(c => !/rgba\(0, 0, 0, 0\)/.test(c));
  const fonts = {}; for (const el of els) { const f = css(el, 'font-family').split(',')[0].replace(/["']/g, '').trim(); if (f) fonts[f] = (fonts[f] || 0) + 1; }
  const h = document.querySelector('h1,h2'); const logos = [];
  document.querySelectorAll('img, svg, link[rel*=icon]').forEach(el => {
    const s = (el.getAttribute('src') || el.getAttribute('href') || '') + ' ' + (el.getAttribute('alt') || '') + ' ' + (el.getAttribute('class') || '') + ' ' + (el.id || '');
    if (/logo|brand|icon/i.test(s)) logos.push({ tag: el.tagName, src: el.currentSrc || el.src || el.href || null, svg: el.tagName === 'svg' ? el.outerHTML.slice(0, 20000) : null });
  });
  return { title: document.title, h1: h && h.innerText.slice(0, 200), body_bg: css(document.body, 'background-color'),
    colors: Object.entries(cnt).sort((a, b) => b[1] - a[1]).slice(0, 12).map(x => x[0]),
    buttons: [...new Set(btn)].slice(0, 6), fonts: Object.entries(fonts).sort((a, b) => b[1] - a[1]).slice(0, 5).map(x => x[0]),
    heading_font: h ? css(h, 'font-family') : null, logos: logos.slice(0, 8) };
}"""


def goto(pg, url):
    try:
        pg.goto(url, wait_until='load', timeout=60000)
    except Exception as e:
        sys.exit(f'Could not open {url}: {str(e).splitlines()[0]}\n'
                 'If this sandbox blocks the site, ask the user for screenshots and the logo file instead.')
    try:
        pg.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        pass                                   # some sites never go idle; 'load' is enough
    pg.wait_for_timeout(1000)


def cmd_capture(a):
    from playwright.sync_api import sync_playwright
    p = Path(a.project)
    (p / 'assets').mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = launch(pw)
        pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        goto(pg, a.url)
        pg.screenshot(path=str(p / 'assets' / 'site_hero.png'))
        pg.screenshot(path=str(p / 'assets' / 'site_full.png'), full_page=True)
        info = pg.evaluate(CAPTURE_JS)
        for i, lg in enumerate(info['logos']):
            try:
                if lg.get('svg'):
                    (p / 'assets' / f'logo_{i}.svg').write_text(lg['svg']); lg['saved'] = f'assets/logo_{i}.svg'
                elif lg.get('src') and not lg['src'].startswith('data:'):
                    r = pg.request.get(lg['src'])
                    ext = os.path.splitext(lg['src'].split('?')[0])[1][:5] or '.png'
                    (p / 'assets' / f'logo_{i}{ext}').write_bytes(r.body()); lg['saved'] = f'assets/logo_{i}{ext}'
                lg.pop('svg', None)
            except Exception as e:  # keep going; a missing logo is reported below
                lg['error'] = str(e)
        pg2 = b.new_page(viewport={'width': 430, 'height': 932}, device_scale_factor=2)
        goto(pg2, a.url)
        pg2.screenshot(path=str(p / 'assets' / 'site_mobile.png'))
        b.close()
    info['url'] = a.url
    (p / 'assets' / 'site.json').write_text(json.dumps(info, indent=2))
    print(json.dumps({k: info[k] for k in ('title', 'h1', 'colors', 'buttons', 'fonts')}, indent=1))
    print('Saved: assets/site_hero.png, site_full.png, site_mobile.png, site.json, logos:',
          [l.get('saved') for l in info['logos'] if l.get('saved')] or 'none found')
    print('NOTE: also screenshot the real product UI (logged-in screens) if the client can share them.')


def cmd_brand_from_site(a):
    p = Path(a.project).resolve()
    info = json.loads((p / 'assets' / 'site.json').read_text())
    base = json.loads((SKILL / 'brands' / 'studio' / 'brand.json').read_text())

    def hexify(c):
        import re
        m = re.findall(r'[\d.]+', c or '')
        return '#%02X%02X%02X' % tuple(int(float(x)) for x in m[:3]) if len(m) >= 3 else None
    cols = [h for h in (hexify(c) for c in info['colors']) if h]
    btn = [h for h in (hexify(c) for c in info['buttons']) if h]
    lum = lambda h: sum(int(h[i:i + 2], 16) * w for i, w in ((1, .299), (3, .587), (5, .114))) / 255
    bg = hexify(info.get('body_bg')) or (cols[0] if cols else base['colors']['bg'])
    dark = [c for c in cols if lum(c) < 0.25] or ['#111111']
    light = [c for c in cols if lum(c) > 0.85] or ['#F5F5F5']
    sat = lambda h: (max(int(h[i:i + 2], 16) for i in (1, 3, 5)) - min(int(h[i:i + 2], 16) for i in (1, 3, 5))) / 255
    accents = sorted(set(btn + cols), key=sat, reverse=True)
    accent = accents[0] if accents and sat(accents[0]) > 0.25 else base['colors']['accent']
    brand = dict(base)
    brand.update({'name': a.slug, 'url': info['url'].split('://')[-1].rstrip('/'), 'tagline': info.get('h1') or '', 'cta': 'Try it free',
                  'colors': {'bg': dark[0], 'paper': light[0], 'ink': dark[0], 'inkOnDark': light[0],
                             'muted': '#8A8A8A', 'line': '#2A2A2A', 'accent': accent,
                             'accent2': accents[1] if len(accents) > 1 else accent},
                  'site_fonts': info['fonts'], 'site_bg': bg,
                  'notes': 'Auto-drafted from the site. Check every color against the real brand. Fonts are the house '
                           'fonts until the client\'s font files are added to brand/fonts/.'})
    logos = [l['saved'] for l in info['logos'] if l.get('saved')]
    bd = p / 'brand'; (bd / 'fonts').mkdir(parents=True, exist_ok=True)
    for f in (SKILL / 'brands' / 'studio' / 'fonts').iterdir():
        shutil.copy(f, bd / 'fonts' / f.name)
    if logos:
        shutil.copy(p / logos[0], bd / ('logo' + Path(logos[0]).suffix))
        brand['logo'] = 'logo' + Path(logos[0]).suffix
    else:
        brand['logo'] = None
    (bd / 'brand.json').write_text(json.dumps(brand, indent=2))
    cfg = json.loads((p / 'project.json').read_text()); cfg['brand'] = 'brand'
    (p / 'project.json').write_text(json.dumps(cfg, indent=2))
    print(json.dumps(brand['colors'], indent=1))
    print(f'Wrote {bd}/brand.json (site fonts seen: {info["fonts"]}). Review colors and the logo before animating.')


# ------------------------------------------------------------------ stills
def cmd_stills(a):
    from playwright.sync_api import sync_playwright
    p, cfg = load_project(a.project)
    fmt = fmt_list(cfg, a.format)[0]
    srv, url, size = build_page(p, cfg, fmt, debug=not a.clean, fps=cfg.get('fps', 30))
    sdir = p / 'out' / 'stills'
    shutil.rmtree(sdir, ignore_errors=True); sdir.mkdir(parents=True)
    warnings = []
    with sync_playwright() as pw:
        b = launch(pw)
        page = open_page(b, url, size)
        meta = page.evaluate('window.meta()')
        dur = meta['duration']
        if a.at:
            times = [float(x) for x in a.at.split(',')]
        elif a.beats:
            spb = 60 / meta['bpm']; times = [round(i * spb + spb * 0.6, 3) for i in range(int(dur / spb))]
        else:
            times = [round(x * a.every + a.every * 0.5, 3) for x in range(int(dur / a.every))]
        W, H = size; mx, my = W * 0.04, H * 0.04
        for i, t in enumerate(times):
            d = page.evaluate(f'window.frame({t}, 1)')
            (sdir / f'{i:03d}.png').write_bytes(data_url_bytes(d))
            bx = page.evaluate('window.boxes()')
            for k in bx:
                if k['x0'] < mx or k['y0'] < my or k['x1'] > W - mx or k['y1'] > H - my:
                    vis = (max(0, min(k['x1'], W) - max(k['x0'], 0)) * max(0, min(k['y1'], H) - max(k['y0'], 0)) /
                           max(1, (k['x1'] - k['x0']) * (k['y1'] - k['y0'])))
                    if vis > 0.6:   # mostly on screen; things leaving the frame are fine
                        warnings.append(f'{t:6.2f}s  text outside safe area: "{k["str"]}"')
            for i1 in range(len(bx)):
                for i2 in range(i1 + 1, len(bx)):
                    A, B = bx[i1], bx[i2]
                    ox = min(A['x1'], B['x1']) - max(A['x0'], B['x0']); oy = min(A['y1'], B['y1']) - max(A['y0'], B['y0'])
                    if ox > 6 and oy > 6:
                        warnings.append(f'{t:6.2f}s  text overlap: "{A["str"]}" x "{B["str"]}"')
        b.close()
    srv.close()
    cols = 6 if W >= H else 8
    rows = math.ceil(len(times) / cols)
    tw = 320 if W >= H else 200
    ff = ffmpeg_bin()
    subprocess.run([ff, '-v', 'error', '-y', '-framerate', '1', '-i', str(sdir / '%03d.png'),
                    '-vf', f'scale={tw}:-1,pad=iw+6:ih+6:3:3:color=0x333333,tile={cols}x{rows}',
                    '-frames:v', '1', str(p / 'out' / f'stills_{fmt.replace(":", "x")}.png')], check=True)
    uniq = sorted(set(warnings))
    (p / 'out' / 'layout_warnings.txt').write_text('\n'.join(uniq) + ('\n' if uniq else ''))
    print(f'STILLS: out/stills_{fmt.replace(":", "x")}.png ({len(times)} frames, {cols} across) + out/stills/NNN.png')
    print(f'LAYOUT WARNINGS: {len(uniq)}' + ('' if not uniq else '\n  ' + '\n  '.join(uniq[:25])))


# ------------------------------------------------------------------ audio
def cmd_audio(a):
    import audio as au
    import numpy as np
    p, cfg = load_project(a.project)
    ff = ffmpeg_bin()
    (p / 'audio').mkdir(exist_ok=True)
    mus = cfg.get('music', {'source': 'synth'})
    if mus.get('source') == 'file':
        track = p / mus['path']
        bj = au.beats_from_file(ff, track, mus)
        # Trim the track so its first downbeat lands on t = 0 (the film's beat 0).
        off = bj['offset']
        for k in ('beats', 'downbeats', 'hits'):
            bj[k] = [round(x - off, 4) for x in bj[k] if x - off >= -1e-6]
        bj['trim'], bj['offset'] = off, 0
        (p / 'beats.json').write_text(json.dumps(bj, indent=1))
        print(f"BEATS: {bj['bpm']:.1f} BPM ({'measured' if bj['measured'] else 'from project.json'})")
    elif (p / 'beats.json').exists():
        (p / 'beats.json').unlink()      # a stale measured grid would warp a synth film
    meta = get_meta(p, cfg)
    dur = meta['duration']
    if mus.get('source', 'synth') == 'synth':
        (p / 'beats.json').write_text(json.dumps(au.synth_beats(meta['bpm'], dur), indent=1))
        music = au.synth_music(dur, meta['bpm'], drop_bar=mus.get('drop_bar', 1), end_t=mus.get('end'),
                               progression=mus.get('progression', 'AFCG'))
    elif mus.get('source') == 'file':
        trim = json.loads((p / 'beats.json').read_text()).get('trim', 0)
        x = au.read_wav(ff, p / mus['path'])[int(trim * au.SR): int((trim + dur + 1.5) * au.SR)]
        fade = int(1.0 * au.SR); x = x.copy(); x[-fade:] *= np.linspace(1, 0, min(fade, len(x)))
        music = x
    else:
        music = np.zeros(int((dur + 1.5) * au.SR), np.float32)
    sfx = au.render_sfx(meta['cues'], dur)
    voice = np.zeros_like(sfx)
    v = cfg.get('voice', {'source': 'none'})
    if v.get('source') in ('file', 'elevenlabs'):
        src = p / v['path'] if v['source'] == 'file' else au.elevenlabs(str(p), v)
        au.add(voice, v.get('start', 0), au.read_wav(ff, src) * v.get('gain', 1.0))
    n = int((dur + 1.5) * au.SR)
    pad = lambda x: np.pad(x, (0, max(0, n - len(x))))[:n]
    duck = cfg.get('voice', {}).get('duck', 0.45) if voice.any() else 1.0
    mix = pad(music) * mus.get('gain', 0.8) * duck + pad(sfx) * cfg.get('sfx', {}).get('gain', 0.9) + pad(voice)
    au.write_wav(p / 'audio' / 'music.wav', pad(music)); au.write_wav(p / 'audio' / 'sfx.wav', pad(sfx))
    peak = float(np.abs(mix).max()) or 1
    au.write_wav(p / 'audio' / 'mix_raw.wav', mix / peak * 0.9)
    au.loudnorm(ff, p / 'audio' / 'mix_raw.wav', p / 'audio' / 'mix.wav', cfg.get('loudness', -14))
    lufs = au.measure_lufs(ff, p / 'audio' / 'mix.wav')
    print(f'AUDIO: audio/mix.wav  {dur:.2f}s, {len(meta["cues"])} SFX cues, music={mus.get("source", "synth")}, '
          f'voice={v.get("source")}, loudness {lufs:.1f} LUFS')


# ------------------------------------------------------------------ render
def _render_chunk(job):
    from playwright.sync_api import sync_playwright
    url, size, fps, sub, shutter, f0, f1, seg, crf = job
    ff = ffmpeg_bin()
    proc = subprocess.Popen([ff, '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'png', '-i', '-',
                             '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf), '-pix_fmt', 'yuv420p',
                             '-r', str(fps), str(seg)], stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        b = launch(pw)
        page = open_page(b, url, size)
        for f in range(f0, f1):
            d = page.evaluate(f'window.frame({f / fps}, {sub}, {shutter})')
            proc.stdin.write(data_url_bytes(d))
        b.close()
    proc.stdin.close(); proc.wait()
    return seg


def cmd_render(a):
    p, cfg = load_project(a.project)
    ff = ffmpeg_bin()
    fps = a.fps or (30 if a.draft else cfg.get('fps', 30))
    sub = 1 if a.draft else (a.blur if a.blur is not None else cfg.get('blur', 4))
    workers = a.workers or max(1, min(6, (os.cpu_count() or 2) - 1))
    for fmt in fmt_list(cfg, a.format):
        t0 = time.time()
        srv, url, size = build_page(p, cfg, fmt, draft=a.draft, fps=fps)
        meta = get_meta(p, cfg, fmt)
        total = int(round(meta['duration'] * fps))
        tmp = Path(tempfile.mkdtemp(prefix='mr_'))
        step = math.ceil(total / workers)
        jobs = [(url, size, fps, sub, cfg.get('shutter', 0.5), i, min(total, i + step), tmp / f'seg{i:06d}.mp4', 16)
                for i in range(0, total, step)]
        print(f'RENDER {fmt} {size[0]}x{size[1]} {fps}fps blur={sub} frames={total} workers={len(jobs)}', flush=True)
        with Pool(len(jobs)) as pool:
            for k, _ in enumerate(pool.imap_unordered(_render_chunk, jobs), 1):
                print(f'  chunk {k}/{len(jobs)} done ({time.time() - t0:.0f}s)', flush=True)
        srv.close()
        (tmp / 'list.txt').write_text(''.join(f"file '{j[7]}'\n" for j in jobs))
        tag = fmt.replace(':', 'x') + ('_draft' if a.draft else '')
        silent = p / 'out' / f'silent_{tag}.mp4'
        (p / 'out').mkdir(exist_ok=True)
        subprocess.run([ff, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'list.txt'), '-c', 'copy',
                        str(silent)], check=True)
        shutil.rmtree(tmp, ignore_errors=True)
        final = p / 'out' / f'final_{tag}.mp4'
        mix = p / 'audio' / 'mix.wav'
        if mix.exists():
            subprocess.run([ff, '-v', 'error', '-y', '-i', str(silent), '-i', str(mix), '-map', '0:v', '-map', '1:a',
                            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f"{meta['duration']:.3f}",
                            '-movflags', '+faststart', str(final)], check=True)
        else:
            print('  (no audio/mix.wav yet; run: studio.py audio PROJECT) -> silent video only')
            shutil.copy(silent, final)
        print(f'VIDEO: {final}  ({meta["duration"]:.2f}s, rendered in {time.time() - t0:.0f}s)', flush=True)


# ------------------------------------------------------------------ qa
def cmd_qa(a):
    from playwright.sync_api import sync_playwright
    p, cfg = load_project(a.project)
    ff = ffmpeg_bin()
    for fmt in fmt_list(cfg, a.format):
        tag = fmt.replace(':', 'x')
        vid = p / 'out' / f'final_{tag}.mp4'
        if not vid.exists():
            sys.exit(f'{vid} not found. Render first.')
        o = p / 'out'
        W, H = FORMATS[fmt]
        meta = get_meta(p, cfg, fmt)
        cols = 6 if W >= H else 8
        rows = math.ceil(meta['duration'] * 2 / cols)
        run = lambda *x: subprocess.run([ff, '-v', 'error', '-y', *x], check=True)
        run('-i', str(vid), '-vf', f'fps=2,scale={320 if W >= H else 200}:-1,tile={cols}x{rows}', '-frames:v', '1',
            str(o / f'contact_{tag}.png'))
        # phone test: how it reads when the video is ~360 px wide (16:9 in a feed)
        run('-i', str(vid), '-vf', f'fps=1,scale=360:-1,tile=5x{math.ceil(meta["duration"] / 5)}', '-frames:v', '1',
            str(o / f'phone_{tag}.png'))
        # strips around every scene cut: catch pops, overlaps, dead frames
        cuts = sorted({round(s[0], 3) for s in meta['scenes'] if s[0] > 0})
        for i, c in enumerate(cuts[:12]):
            run('-ss', f'{max(0, c - 0.2):.3f}', '-i', str(vid), '-vf', 'fps=30,scale=240:-1,tile=12x1', '-frames:v', '1',
                str(o / f'strip_{tag}_{i:02d}_{c:.2f}s.png'))
        if meta.get('loop'):
            run('-stream_loop', '1', '-i', str(vid), '-c', 'copy', str(o / f'loop_check_{tag}.mp4'))
        # dead time: 1.5 s or more without visible change
        fd = subprocess.run([ff, '-hide_banner', '-i', str(vid), '-vf', 'freezedetect=n=0.002:d=1.5', '-map', '0:v',
                             '-f', 'null', '-'], capture_output=True, text=True).stderr
        frozen = [l.split('freeze_start: ')[1].strip() for l in fd.splitlines() if 'freeze_start' in l]
        # determinism: same frame from two fresh browsers must hash the same
        srv, url, size = build_page(p, cfg, fmt, fps=cfg.get('fps', 30))
        hashes = []
        tcheck = round(meta['duration'] * 0.37, 3)
        with sync_playwright() as pw:
            for _ in range(2):
                b = launch(pw)
                pg = open_page(b, url, size)
                pg.evaluate(f'window.frame({tcheck / 2}, 1)')   # disturb any hidden state first
                hashes.append(hashlib.md5(data_url_bytes(pg.evaluate(f'window.frame({tcheck}, 1)'))).hexdigest())
                b.close()
        srv.close()
        import audio as au
        lufs = au.measure_lufs(ff, vid) if (p / 'audio' / 'mix.wav').exists() else None
        lines = [f'QA {fmt}',
                 f'  contact sheet : out/contact_{tag}.png (2 fps)',
                 f'  phone test    : out/phone_{tag}.png (360 px wide)',
                 f'  cut strips    : {len(cuts[:12])} in out/strip_{tag}_*.png',
                 f'  dead time     : ' + ('none' if not frozen else 'FROZEN from ' + ', '.join(f'{float(x):.2f}s' for x in frozen)),
                 f'  deterministic : ' + ('yes' if hashes[0] == hashes[1] else 'NO - frame differs between runs (Math.random, Date or carried state?)'),
                 f'  loudness      : ' + (f'{lufs:.1f} LUFS' if lufs is not None else 'no audio')]
        (o / f'qa_{tag}.txt').write_text('\n'.join(lines) + '\n')
        print('\n'.join(lines))


def cmd_all(a):
    cmd_audio(a); cmd_render(a); cmd_qa(a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('setup')
    n = sp.add_parser('new'); n.add_argument('project'); n.add_argument('--brand', default='studio')
    n.add_argument('--template', default='reel'); n.add_argument('--force', action='store_true')
    c = sp.add_parser('capture'); c.add_argument('url'); c.add_argument('project')
    bs = sp.add_parser('brand-from-site'); bs.add_argument('project'); bs.add_argument('slug')
    s = sp.add_parser('stills'); s.add_argument('project'); s.add_argument('--every', type=float, default=0.5)
    s.add_argument('--at'); s.add_argument('--beats', action='store_true'); s.add_argument('--format')
    s.add_argument('--clean', action='store_true', help='no timestamp overlay')
    au = sp.add_parser('audio'); au.add_argument('project')
    for name in ('render', 'all'):
        r = sp.add_parser(name); r.add_argument('project'); r.add_argument('--format'); r.add_argument('--draft', action='store_true')
        r.add_argument('--fps', type=int); r.add_argument('--blur', type=int); r.add_argument('--workers', type=int)
    q = sp.add_parser('qa'); q.add_argument('project'); q.add_argument('--format')
    a = ap.parse_args()
    {'setup': cmd_setup, 'new': cmd_new, 'capture': cmd_capture, 'brand-from-site': cmd_brand_from_site,
     'stills': cmd_stills, 'audio': cmd_audio, 'render': cmd_render, 'qa': cmd_qa, 'all': cmd_all}[a.cmd](a)


if __name__ == '__main__':
    main()
