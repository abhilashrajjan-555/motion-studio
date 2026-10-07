# UI-morph spec (one shape, never cut)

    <inputs>
    Ask me for: product + URL, 8 to 12 UI states that tell its story, the real data shown
    in each state, brand colors + fonts + one accent, a track near 120 BPM (or synthesize), formats.
    </inputs>

    <direction>
    Product-film UI motion. One container never cuts: every state is the same element changing
    size, radius and fill while its content swaps behind a short blur. A cursor drives every change.
    Warm neutral canvas, one accent. Springs with at most a tiny overshoot.
    Banned: bouncy easing, glows, gradients on UI chrome, particle bursts, dead time.
    </direction>

    <structure>
    120 BPM, 8 bars, something happens on every beat.
    logo → CTA button → email field (typed) → loader → success check → dashboard card
    → chart draws itself → tooltip on hover → ⌘K palette → toast → logo.
    </structure>

    <build>
    Use the motion-reel engine. The container rect is M.trackObj over the state list
    (one spring per change). Text inside uses M.swapAlpha: in after the morph starts,
    out before the next one. Tab indicators use M.stretch. Cursor = M.trackObj + D.cursor + D.ripple.
    Set FILM.loop = true; the last frame must equal the first (cursor position included).
    </build>

    <start>
    Ask for the inputs, then show me the state list on the beat grid before writing code.
    </start>
