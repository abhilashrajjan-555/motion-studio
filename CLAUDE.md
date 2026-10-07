# Motion Studio: rules for working on this repo

The owner is not a coder. Keep changes small, test them by rendering, and explain results in plain words.

## Layout
- `motion-reel/` is the skill (uploaded as a zip). Everything it needs must live inside it.
- `examples/studio-reel/` is the regression project. After any engine or template change, run:
  `python3 motion-reel/engine/studio.py stills examples/studio-reel` and look at the sheet,
  then `audio`, `render --format all`, and `qa` for each format. QA must say: dead time none,
  deterministic yes, loudness -14 ±1.
- Rebuild `dist/motion-reel.zip` with `./build.sh` before committing a skill change.

## Render contract
- A film is a pure function of time. No Math.random (use M.rng), no Date, no timers,
  no CSS transitions, no state carried between frames.
- Films draw in virtual units (short side = 1080) and lay out from S.W / S.H / S.fmt.
- Films are authored on a steady FILM.bpm grid; runtime.js warps real time onto it when
  a measured track exists. Keep that contract: meta() returns real seconds.

## Look
- Banned defaults: centered title on gradient, everything fading in, corner labels and
  frame borders, glow on UI chrome, generic particle bursts.
- Springs from lib.js only. Tiny overshoot on UI, none on type.

## Don't
- Don't add dependencies beyond playwright + numpy (librosa optional).
- Don't commit rendered intermediates (`silent_*.mp4`, `out/stills/`, `build/`).
