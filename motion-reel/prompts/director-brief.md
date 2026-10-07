# Director's brief (long films, 45 s – 3 min, multi-session)

    You are the director, animator, sound designer and render engineer for a [DURATION] film
    made in code with the motion-reel skill. Treat this as a multi-session production.
    Don't rush to a final render.

    ## The film in one line
    [LOGLINE. What the viewer should feel at the end.]

    ## References and inputs
    - ./refs/ : [video / frames / image library]. Take the grammar, never the content.
    - ./audio/track.wav : [use unchanged | none → synthesize]. Measure beats first (studio.py audio).
    - Voice: [none | audio/vo.wav | ElevenLabs voice_id ..., key in .env]. Budget: [$X].

    ## Look
    [3-5 lines: palette, type, texture, camera language. Banned looks.]

    ## Beat sheet
    0:00-0:02  hook: [the single most striking image]
    0:02-0:10  [act 1]
    ...        a new visual payoff every 3-5 seconds
    [END]      CTA / final image held 1.5 s+

    ## Workflow, with gates
    1. docs/style_guide.md + docs/shotlist.md (every shot: time, camera, text, SFX). Show me.
    2. Build stills for every shot. Contact sheet. Critique (prompts/critique.md).
    3. Draft render (--draft) with audio. Fix pacing before polish.
    4. Full animation, polish pass, sound pass, final render, QA.
    5. Split long films into chapter files (film.js can load several scene arrays);
       write docs/ANIMATION_GUIDE.md first so every chapter uses the same style.

    ## Critique loop (every chapter, at least 3 rounds)
    Score 1-10 on hook, readability at 360 px wide, motion, composition, depth, sound sync,
    polish. Log scores + 3 biggest problems in docs/review_log.md. Fix. Repeat until all are 8+.

    ## Deliverables
    out/final_16x9.mp4 · out/contact_16x9.png · poster.png · docs/shotlist.md · review_log.md
