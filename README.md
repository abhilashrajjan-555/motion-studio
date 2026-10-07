# Motion Studio

A Claude skill, `motion-reel`, that makes motion-design videos entirely in code: product launch films, brand reels, showreels, motion ads and UI demos. It adds synthesized music and sound effects on the beat, and has Claude check its own frames before it shows you anything.

You describe the video. Claude writes it as a small program, renders every frame in a headless browser, adds sound, checks the result, and hands you an MP4.

**What's in this repo**

| Folder | What it is |
|---|---|
| `motion-reel/` | The skill. This folder is what you upload to Claude. |
| `motion-reel/engine/` | The render engine: `studio.py` (commands), `audio.py` (sound), `runtime/` (animation library) |
| `motion-reel/templates/reel/` | The starting film: hook, pitch, product UI, 3 features, a number, logo + CTA |
| `motion-reel/prompts/` | Briefs you can copy: brand reel, reference, UI-morph spec, director's brief, critique |
| `motion-reel/brands/studio/` | The house brand (placeholder name "Studio", colors, fonts) |
| `examples/studio-reel/` | The demo project, with its rendered videos in `out/` |
| `dist/motion-reel.zip` | The skill packed for upload |

---

## Step 1. Install the skill (once, about 5 minutes)

1. Download `dist/motion-reel.zip` from this repo. On GitHub: open the file, then click **Download raw file**.
2. Open **claude.ai → Settings → Capabilities**. Make sure **Code execution and file creation** is turned on.
3. On the same page, under **Skills**, click **Upload skill** and choose `motion-reel.zip`. (Menu names can move slightly between app versions.)
4. Make sure the `motion-reel` skill shows as **on**.

The same skill works in **Cowork**. Use Cowork for real jobs: it can save projects to a folder on your computer, so you can come back and edit a video later. In normal claude.ai chat, the workspace is wiped after the chat, so only the final files you download are kept.

## Step 2. Make your first video (test run)

Start a new chat (or Cowork task) and paste:

```
Use the motion-reel skill. Make a 20-second 16:9 reel for our studio using the house
brand. Synthesized music. Show me the shot list first.
```

What happens:

1. Claude installs the engine (about 1 minute the first time in each chat).
2. It shows you a **shot list**: what's on screen every 2 seconds. Reply "OK" or ask for changes.
3. It builds the film, renders **contact sheets** (a grid of frames), scores them 1–10, and fixes the weak spots. It repeats this at least 3 times.
4. It renders the final MP4 (about 1–2 minutes for 20 seconds) and runs the QA checks.
5. You get the MP4, a contact sheet and a poster frame.

## Step 3. Make a client video

Copy `motion-reel/prompts/brand-reel.md`, fill in the brackets, and paste it. The most important inputs:

- **The product URL.** Claude screenshots the site and pulls colors and the logo.
- **Real product screenshots** (attach them). The skill will not invent a client's UI.
- **A reference**: one frame or a short clip of a video whose style you like. This is the biggest quality lever.
- **One real number** that proves the product works, with its source. If you don't have one, that beat is skipped. Claude won't make one up.

## Step 4. Check before you send it to anyone

Watch the full video once with sound, then check:

- [ ] Every claim and number is real (the demo's "48h" is a placeholder)
- [ ] Logo, colors and product screens are the client's real ones
- [ ] Text reads on a phone (open `out/phone_16x9.png`)
- [ ] The CTA stays on screen for at least 1.5 seconds

---

## Adding things later

**Licensed music.** Put the track in the project as `audio/track.wav` (or .mp3) and tell Claude: *"use audio/track.wav as the music."* Claude sets this in `project.json`:
```json
"music": {"source": "file", "path": "audio/track.wav", "bpm": 120}
```
Claude measures the beats, and the animation stretches to land on them, so a template written at 120 BPM still hits the cuts on a 100 BPM song. If the big moments land half a bar off, give Claude the time of the song's first strong downbeat (for example `"first_downbeat": 0.42`).

**ElevenLabs voiceover.** When you have a key:
1. Create a file called `.env` in the project folder containing one line: `ELEVENLABS_API_KEY=your-key`. Never paste the key into a chat you might screenshot.
2. Tell Claude: *"add a voiceover with ElevenLabs voice ID ___ saying: ___."* It sets:
```json
"voice": {"source": "elevenlabs", "voice_id": "...", "text": "...", "start": 0.5}
```
The music automatically drops in volume under the voice. **Note:** the ElevenLabs connection is written but hasn't been tested with a real key yet. Test it on a throwaway project first.

**Your own voice recording.** Put it at `audio/vo.wav` and use `"voice": {"source": "file", "path": "audio/vo.wav", "start": 0.5}`.

**Other formats.** Say *"also render 9:16 and 1:1."* All formats come from the same timeline. Nothing is cropped.

**Your company name and brand.** Edit `motion-reel/brands/studio/brand.json` (name, tagline, CTA, URL, colors). Add a logo file next to it and set `"logo": "logo.png"`. Then rebuild the zip (below) and upload it again. Or ask Claude in a code session: *"update the house brand to name X, colors Y, logo attached."*

## Updating the skill

After any change to the `motion-reel/` folder, rebuild the zip and upload it again in Settings:

```bash
./build.sh          # writes dist/motion-reel.zip
```

## Limits to know

- **Rendering speed:** about 75 seconds for a 20-second 1080p video on 4 CPU cores. A 2-minute film takes around 8 minutes.
- **Website capture** only works if Claude's sandbox can reach the site. If it can't, Claude will ask you for screenshots and the logo file.
- **Downbeat detection** on supplied tracks is a best guess. The tempo is reliable; which beat starts the bar sometimes needs `first_downbeat`.
- **Synthesized music** is clean and on the beat, but it's a bed, not a composed score. For hero films, a licensed track is worth it.

## When to use which skill

| Need | Skill |
|---|---|
| Narrated explainer for your YouTube or LinkedIn, with thumbnails | `explainer-video` |
| Product reel, launch film, showreel, motion ad, client work | `motion-reel` |

## Commands (for Claude or a code session)

```
python3 engine/studio.py setup                       check/install ffmpeg, Chromium, numpy
python3 engine/studio.py new PROJECT [--brand studio]
python3 engine/studio.py capture URL PROJECT         screenshots, colors, logo
python3 engine/studio.py brand-from-site PROJECT SLUG
python3 engine/studio.py stills PROJECT --every 0.5  contact sheet + layout warnings
python3 engine/studio.py audio PROJECT               music + SFX + voice, -14 LUFS
python3 engine/studio.py render PROJECT --format all [--draft]
python3 engine/studio.py qa PROJECT                  contact, phone test, cut strips, dead time, determinism, loudness
```
