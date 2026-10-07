---
name: motion-reel
description: "Make a motion-design video (MP4) rendered entirely from code: product launch film, brand reel, showreel, motion ad, animated UI demo or logo sting, with synthesized music and SFX on the beat. Use when the user asks for a launch video, product reel, showreel, motion graphics, promo or ad video, animated product demo, or a client video for the studio, in any aspect ratio (16:9 default, 9:16, 1:1). Not for narrated YouTube explainers (use explainer-video)."
---

# Motion reel

Every film is a program: `film.js` defines a pure function of time, a headless browser paints each frame, ffmpeg encodes. The prompt is 10% of the result; the harness (reference, beat grid, critique loop) is the other 90%. Never skip the critique loop.

## 0. Install (once per session)

```bash
SK=$(dirname "$(find / -name studio.py -path '*motion-reel/engine/*' 2>/dev/null | head -1)")/..
mkdir -p ~/mr && cp -r "$SK"/engine "$SK"/brands "$SK"/templates "$SK"/prompts ~/mr/
cd ~/mr && python3 engine/studio.py setup
```
`setup` must print OK for ffmpeg and chromium. If it can't, stop and tell the user what's missing; don't invent a different pipeline.

Where projects live: Cowork → the user's connected folder (projects persist between sessions). claude.ai chat → `~/mr/projects/<slug>`; deliver to `/mnt/user-data/outputs/` because the sandbox is wiped.

## 1. Intake (one AskUserQuestion call; skip what the user already gave; unattended → assume and state it)

1. **Job type**: client product reel · studio's own marketing · showreel · motion ad · UI demo.
2. **Product + URL** (client jobs) and the **one claim/number** that proves it works. Never invent metrics; a missing number becomes a non-numeric beat.
3. **Reference**: a frame, a video, an image folder or a named style. Strongly recommend one; without it the model defaults to generic.
4. **Length + formats**: default 20 s, 16:9. Add 9:16 / 1:1 only if asked.
5. **Sound**: synthesized (default) · their licensed track file · voiceover (file or ElevenLabs).

## 2. Project

```bash
cd ~/mr && python3 engine/studio.py new PROJECT --brand studio      # house brand
python3 engine/studio.py capture https://client.com PROJECT          # client jobs: real screenshots + colors + logo
python3 engine/studio.py brand-from-site PROJECT client-slug         # drafts PROJECT/brand/brand.json from the capture
```
- Client jobs: open `assets/site_hero.png` and `site.json`, correct `brand/brand.json` by eye (name, colors, CTA, tagline), open the logo file (a white logo made for a dark header will vanish on `paper`: get the dark version or set the lockup background to `bg`), and list the assets you found to the user before animating. If the sandbox can't reach the site, ask for screenshots and the logo file.
- **Real product UI only.** Put real screenshots in `assets/` (e.g. `assets/screen.png` is picked up by the reel template's UI scene). Never redraw a client's product from imagination. Mock UI is allowed only for the studio's own reels.
- Reference given → follow `prompts/reference.md`: extract frames, write `docs/style_guide.md` (palette hex, type, shot lengths, transitions, camera, texture). Take the grammar, never the content, logos or characters.

## 3. Shot list on the beat grid (checkpoint)

Write `docs/shotlist.md`: one row per shot = time range on the beat grid (120 BPM: beat 0.5 s, bar 2 s), what's on screen, how it enters/exits, camera, text, SFX. Rules: hook in the first 2 s; something new every 2–4 s; one idea per shot; big moments on downbeats; final frame = CTA held ≥1.5 s.
**Show the shot list and wait for OK** (unattended: continue and say so).

## 4. Build film.js

Start from `templates/reel/film.js` (hook → pitch → UI assembles → 3 features in one morphing container → number → logo + CTA). Edit `COPY` first, then timings `T`, then visuals. Read `engine/runtime/lib.js` for the API:
- `M.sp(t, 'snap'|'ui'|'base'|'heavy'|'play')` closed-form springs; `M.track(t, [[time, value]...])` for values with several targets (one spring per change, never restart); `M.trackObj` for rects/points; `M.stretch` for indicators; `M.swapAlpha` for content inside a morphing box.
- `D.words` kinetic type (masked rise, no fades) · `D.text` · `D.box` · `D.image` · `D.cursor` + `D.ripple` · `D.num`.
- Scene: `{name, from, to, draw(S, lt, dur)}`; `S = {g, W, H, t, B (beats), A (assets by filename), BRAND, fmt}`. Virtual units: the short side is always 1080. Layout from `S.W/S.H/S.fmt`, never fixed pixels, so every format works.
- `FILM.cues(B)` = SFX list `{t, type, gain}`; types: click tick type pop thump impact whoosh swish rise success.

**Hard rules**: no `Math.random` (use `M.rng(seed)`), no `Date`, timers, CSS transitions or state carried between frames. Banned looks: centered title on a gradient, everything fading in, corner labels / frame borders, glow on UI chrome, generic particle bursts, slides instead of springs. One display face + one UI face, one accent color.

## 5. Critique loop (at least 3 rounds, before any full render)

```bash
python3 engine/studio.py stills PROJECT --every 0.5        # out/stills_16x9.png + LAYOUT WARNINGS
```
Open the contact sheet and the worst individual stills (`out/stills/NNN.png`) and judge them as a harsh motion director (`prompts/critique.md`). Score 1–10: hook (first 2 s) · readability at phone size · motion quality · variety · composition · brand accuracy · sound sync (after audio). Log scores + the 3 biggest problems with timestamps in `docs/review_log.md`. Fix, re-run stills. Repeat until every score is 8+. Treat each LAYOUT WARNING as a problem unless it's a deliberate overshoot or exit.

## 6. Sound, render, QA

```bash
python3 engine/studio.py audio  PROJECT                 # beats.json, music + SFX + voice, mix at -14 LUFS
nohup python3 engine/studio.py render PROJECT --format all > PROJECT/render.log 2>&1 &   # poll for "VIDEO:"
python3 engine/studio.py qa     PROJECT --format 16:9   # contact sheet, phone test, cut strips, dead time, determinism, loudness
```
`render --draft` = half resolution, no motion blur (quick pacing check). A 20 s 16:9 film renders in about 1–2 min on 4 cores.
`project.json` controls sound: `music.source` = `synth` | `file` (+`path`, `bpm`, `offset`) | `none`; `voice.source` = `none` | `file` | `elevenlabs` (key in `PROJECT/.env` as `ELEVENLABS_API_KEY`, never in a prompt). With a supplied track, re-run `audio` first: it writes the measured beat grid the film reads via `S.B`.
Open the QA contact sheet, the phone test and every cut strip. QA must say: dead time none, deterministic yes, loudness −14 ±1. Fix and re-render otherwise.

## 7. Deliver

Copy to the outputs folder: `final_16x9.mp4` (+ other formats), `contact_16x9.png`, a poster frame (`stills --at <best moment> --clean`, then copy that PNG as `poster.png`), and `docs/shotlist.md`. Report in ≤5 lines: length, formats, sound source, final critique scores, anything placeholder or unverified (claims, numbers, mock UI), and the one thing you'd improve next.
