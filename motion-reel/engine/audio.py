"""Sound for motion-reel: synthesized score, synthesized SFX, optional track,
optional voiceover, and a loudness-normalized mix.

Music sources (project.json "music"):
  {"source": "synth", "style": "pulse", "gain": 0.8}       default, made in code
  {"source": "file", "path": "audio/track.wav", "bpm": 120, "offset": 0.0}
        a licensed track. Beats are measured with librosa when installed,
        otherwise bpm + offset from here are used.
  {"source": "none"}

Voice sources (project.json "voice"):
  {"source": "none"}                                         default
  {"source": "file", "path": "audio/vo.wav", "start": 0.5}
  {"source": "elevenlabs", "voice_id": "...", "text": "...", "start": 0.5,
   "model_id": "eleven_multilingual_v2"}   needs ELEVENLABS_API_KEY in env or .env
"""
import hashlib
import json
import os
import re
import subprocess
import urllib.request
import wave

import numpy as np

SR = 48000


# ---------------------------------------------------------------- utils
def write_wav(path, x):
    x = np.clip(x, -1, 1)
    data = (x * 32767).astype('<i2').tobytes()
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data)


def read_wav(ffmpeg, path):
    """Decode any audio file to mono float32 at SR via ffmpeg."""
    raw = subprocess.run([ffmpeg, '-v', 'error', '-i', str(path), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, '<i2').astype(np.float32) / 32767


def add(buf, start_s, sig):
    i = int(round(start_s * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    if i < 0:
        sig, i = sig[-i:], 0
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n]


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def soften(x, n=6):
    k = np.hanning(n * 2 + 1); k /= k.sum()
    return np.convolve(x, k, mode='same')


def hipass(x):
    return np.diff(x, prepend=0.0)


# ---------------------------------------------------------------- SFX
def _rng(seed):
    return np.random.default_rng(seed)


def sfx_voice(kind, seed=0):
    """Return (pre_seconds, signal). pre > 0 means the sound peaks at the cue time."""
    r = _rng(seed)
    if kind == 'click':
        t = tt(0.05); return 0, np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90) * 0.5 + hipass(r.normal(0, 1, len(t))) * np.exp(-t * 300) * 0.15
    if kind == 'tick':
        t = tt(0.03); return 0, np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 220) * 0.3
    if kind == 'type':
        t = tt(0.04); f = 2400 + r.uniform(-300, 300)
        return 0, (np.sin(2 * np.pi * f * t) * 0.3 + hipass(r.normal(0, 1, len(t))) * 0.25) * np.exp(-t * 160)
    if kind == 'pop':
        t = tt(0.15); return 0, np.sin(2 * np.pi * (600 + 900 * t) * t) * np.exp(-t * 30) * 0.4
    if kind == 'thump':
        t = tt(0.5); return 0, np.sin(2 * np.pi * (90 - 60 * t) * t) * np.exp(-t * 9) * 0.9
    if kind == 'impact':
        t = tt(1.6)
        low = np.sin(2 * np.pi * (70 - 30 * np.minimum(t, 1)) * t) * np.exp(-t * 3.5)
        burst = soften(r.normal(0, 1, len(t)), 3) * np.exp(-t * 14) * 0.5
        ring = sum(np.sin(2 * np.pi * f * t) for f in (220, 330, 440)) / 3 * np.exp(-t * 2.2) * 0.25
        return 0, (low + burst + ring) * 0.8
    if kind in ('whoosh', 'swish'):
        d = 0.45 if kind == 'whoosh' else 0.2
        t = tt(d); env = np.sin(np.pi * t / d) ** 2
        n = soften(r.normal(0, 1, len(t)), 10 if kind == 'whoosh' else 4)
        return d * 0.6, n * env * (0.9 if kind == 'whoosh' else 0.6)
    if kind == 'rise':
        d = 1.0; t = tt(d); env = (t / d) ** 2
        n = soften(r.normal(0, 1, len(t)), 5) * 0.5 + np.sin(2 * np.pi * (200 * t + 500 * t * t)) * 0.12
        return d, n * env * 0.7
    if kind == 'success':
        t = tt(0.6); a = np.sin(2 * np.pi * 880 * t) * np.exp(-t * 7)
        b = np.zeros_like(t); k = int(0.09 * SR); b[k:] = np.sin(2 * np.pi * 1320 * t[:-k]) * np.exp(-t[:-k] * 6)
        return 0, (a + b) * 0.22
    raise ValueError(f'unknown sfx type "{kind}" (click tick type pop thump impact whoosh swish rise success)')


def render_sfx(cues, dur):
    buf = np.zeros(int((dur + 2) * SR), np.float32)
    for i, c in enumerate(cues):
        pre, sig = sfx_voice(c['type'], seed=i + 1)
        add(buf, c['t'] - pre, sig * c.get('gain', 1.0))
    return buf


# ---------------------------------------------------------------- music
NOTE = {'A': 110.0, 'F': 87.31, 'C': 130.81, 'G': 98.0, 'D': 73.42, 'E': 82.41}
CHORDS = {'A': [0, 3, 7], 'F': [0, 4, 7], 'C': [0, 4, 7], 'G': [0, 4, 7], 'D': [0, 3, 7], 'E': [0, 3, 7]}


def tone(f, dur, harm=4, decay=0.0, attack=0.005, detune=0.0):
    t = tt(dur)
    x = sum(np.sin(2 * np.pi * f * n * (1 + detune) * t) / n for n in range(1, harm + 1))
    env = np.minimum(1, t / max(attack, 1e-4))
    if decay:
        env *= np.exp(-t * decay)
    rel = np.minimum(1, (dur - t) / 0.02)
    return x * env * rel


def synth_music(dur, bpm, drop_bar=1, end_t=None, progression='AFCG', seed=7):
    """A clean, modern 4/4 'pulse' bed. Bar 0 is sparse (hook), the groove
    starts at drop_bar, and everything stops on end_t with an impact chord."""
    spb = 60 / bpm
    end_t = end_t if end_t is not None else dur - spb * 2
    total = int((dur + 2.5) * SR)
    drums = np.zeros(total, np.float32); tonal = np.zeros(total, np.float32)
    duck = np.ones(total, np.float32)
    r = _rng(seed)
    nbeats = int(end_t / spb)

    for b in range(nbeats):
        t0 = b * spb; bar = b // 4; root = progression[bar % len(progression)]
        f0 = NOTE[root]; chord = [f0 * 2 ** (s / 12) for s in CHORDS[root]]
        grooving = bar >= drop_bar
        if grooving or b % 4 == 0:      # kick (bar 0: downbeat only)
            t = tt(0.4); k = np.sin(2 * np.pi * (45 * t + 75 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 7)
            add(drums, t0, k * 0.85)
            dk = 1 - 0.55 * np.exp(-tt(spb) * 9)
            i = int(t0 * SR); duck[i:i + len(dk)] = np.minimum(duck[i:i + len(dk)], dk[:max(0, min(len(dk), total - i))])
        if grooving:
            t = tt(0.06); hat = hipass(hipass(r.normal(0, 1, len(t)))) * np.exp(-t * 70) * 0.06
            add(drums, t0 + spb / 2, hat)
            if b % 2 == 1:              # clap on 2 and 4
                t = tt(0.25); clap = soften(r.normal(0, 1, len(t)), 2) * np.exp(-t * 16) * 0.22
                add(drums, t0, clap + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.1)
            for e in range(2):          # bass, 8ths
                add(tonal, t0 + e * spb / 2, tone(f0 / 2, spb / 2 * 0.9, harm=6, decay=6) * 0.32)
            if bar >= drop_bar + 1:     # arp, 16ths
                for s in range(4):
                    f = chord[(b * 4 + s) % 3] * 4
                    add(tonal, t0 + s * spb / 4, tone(f, spb / 4, harm=3, decay=14) * 0.07)
        if b % 4 == 0:                  # pad, whole bar
            bar_len = min(spb * 4, end_t - t0)
            for f in chord:
                for dt in (-0.003, 0.003):
                    add(tonal, t0, tone(f * 2, bar_len, harm=3, attack=0.25, detune=dt) * 0.035)

    # sparse hook bar: a held low note so bar 0 isn't silent
    add(tonal, 0, tone(NOTE[progression[0]] / 2, min(spb * 4, end_t), harm=5, attack=0.05, decay=0.6) * 0.3)
    # ending: impact chord on end_t
    f0 = NOTE[progression[0]]
    for s in CHORDS[progression[0]] + [12]:
        add(tonal, end_t, tone(f0 * 2 * 2 ** (s / 12), 2.4, harm=4, decay=1.4) * 0.09)
    t = tt(0.9); add(drums, end_t, np.sin(2 * np.pi * (40 * t + 60 * (1 - np.exp(-t * 20)) / 20)) * np.exp(-t * 4) * 0.9)

    mix = drums + tonal * duck
    return mix[: int((dur + 1.5) * SR)]


# ---------------------------------------------------------------- beats
def beats_from_file(ffmpeg, path, cfg):
    try:
        import librosa
        y, sr = librosa.load(str(path), sr=None, mono=True)
        kw = {'start_bpm': float(cfg['bpm'])} if cfg.get('bpm') else {}
        tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units='frames', **kw)
        onset = librosa.onset.onset_strength(y=y, sr=sr)
        low = librosa.onset.onset_strength(y=y, sr=sr, fmax=300, n_mels=16)   # kick drum band
        strength = lambda fr, o=onset: np.interp(fr, np.arange(len(o)), o)
        frames = np.asarray(frames)
        # Fold double-time / half-time detections into 70-160 BPM.
        while len(frames) > 8 and 60 / np.median(np.diff(librosa.frames_to_time(frames, sr=sr))) > 160:
            frames = max((frames[0::2], frames[1::2]), key=lambda f: strength(f).sum())
        while len(frames) > 4 and 60 / np.median(np.diff(librosa.frames_to_time(frames, sr=sr))) < 70:
            frames = np.sort(np.concatenate([frames, ((frames[:-1] + frames[1:]) // 2)]))
        beats = librosa.frames_to_time(frames, sr=sr).round(3).tolist()
        bpm = float(60 / np.median(np.diff(beats))) if len(beats) > 1 else float(np.atleast_1d(tempo)[0])
        peaks = librosa.util.peak_pick(onset, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
        # Downbeat phase: of the 4 possible phases, pick the one whose beats carry the most onset energy.
        # (Heuristic: kicks usually land on the downbeat. Override with "first_downbeat" in project.json.)
        st = strength(frames, low)
        phase = int(np.argmax([st[p::4].mean() for p in range(4)])) if len(beats) >= 8 else 0
        if cfg.get('first_downbeat') is not None:
            phase = int(np.argmin([abs(b - float(cfg['first_downbeat'])) for b in beats]))
        return {'bpm': bpm, 'offset': beats[phase] if beats else 0, 'beats': beats[phase:],
                'downbeats': beats[phase::4], 'hits': librosa.frames_to_time(peaks, sr=sr).round(3).tolist(),
                'measured': True}
    except ImportError:
        if 'bpm' not in cfg:
            raise SystemExit('librosa is not installed and project.json music has no "bpm". '
                             'Run: pip install librosa   or add "bpm" (and "offset") to project.json.')
        bpm, off = float(cfg['bpm']), float(cfg.get('offset', 0))
        return {'bpm': bpm, 'offset': off, 'beats': [], 'downbeats': [], 'hits': [], 'measured': False}


def synth_beats(bpm, dur):
    spb = 60 / bpm
    beats = [round(i * spb, 4) for i in range(int(dur / spb) + 1)]
    return {'bpm': bpm, 'offset': 0, 'beats': beats, 'downbeats': beats[::4], 'hits': [], 'measured': False}


# ---------------------------------------------------------------- voice
def load_env(project):
    for p in (os.path.join(project, '.env'), '.env'):
        if os.path.exists(p):
            for line in open(p):
                m = re.match(r'\s*([A-Z0-9_]+)\s*=\s*"?([^"\n]*)"?', line)
                if m and m.group(1) not in os.environ:
                    os.environ[m.group(1)] = m.group(2)


def elevenlabs(project, v):
    """Text to speech via ElevenLabs. Cached by text + voice. Untested until a key is added."""
    load_env(project)
    key = os.environ.get('ELEVENLABS_API_KEY')
    if not key:
        raise SystemExit('voice.source is "elevenlabs" but ELEVENLABS_API_KEY is not set (env or PROJECT/.env).')
    model = v.get('model_id', 'eleven_multilingual_v2')
    h = hashlib.sha1(f"{v['voice_id']}|{model}|{v['text']}".encode()).hexdigest()[:10]
    out = os.path.join(project, 'audio', f'vo_{h}.mp3')
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{v['voice_id']}?output_format=mp3_44100_128",
            data=json.dumps({'text': v['text'], 'model_id': model}).encode(),
            headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
        with urllib.request.urlopen(req, timeout=120) as r, open(out, 'wb') as f:
            f.write(r.read())
    return out


# ---------------------------------------------------------------- mix
def loudnorm(ffmpeg, src, dst, target=-14.0):
    """Gain to `target` LUFS, then a peak limiter at -1.5 dB. Iterates because
    limiting lowers loudness a little. Returns the final integrated loudness."""
    gain, lufs = 0.0, measure_lufs(ffmpeg, src)
    for _ in range(4):
        gain += target - lufs
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(src), '-af',
                        f'volume={gain:.2f}dB,alimiter=limit=0.84:attack=3:release=80:level=false',
                        '-ar', str(SR), str(dst)], check=True)
        lufs = measure_lufs(ffmpeg, dst)
        if abs(lufs - target) < 0.3:
            break
    return lufs


def measure_lufs(ffmpeg, path):
    p = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path), '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    return float(json.loads(p.stderr[p.stderr.rindex('{'):])['input_i'])
