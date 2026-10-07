# Critique pass

Open out/stills_*.png (or out/contact_*.png after a render), out/phone_*.png and the
individual frames that look weakest. Look at them properly. Be a harsh motion
director, not a proud author.

Score 1-10, each with one line of evidence:
- Hook: does the first 2 s stop a scroll?
- Readability at phone size (360 px wide)
- Motion quality: springs, mass, no dead frames, nothing sliding linearly
- Variety: something new every 2-4 s
- Composition: balance, negative space, nothing cramped against edges
- Brand accuracy: real colors, real logo, real UI
- Sound sync (after `audio`): hits land on cuts and clicks

List the 3 biggest problems with timestamps. Hunt for: text overlapping during swaps,
anything that slides instead of springing, corner labels and frame borders, a
centered title on a gradient, blurry scaled text, a beat where nothing happens,
empty first frame, a CTA that's on screen for less than 1.5 s, a stutter at a loop seam.

Fix them, re-run stills for the affected seconds (--at), log scores and fixes in
docs/review_log.md, and repeat until every score is 8+.
