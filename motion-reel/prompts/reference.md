# Reference → style guide

    Reference: ./refs/[launch.mp4] (and/or ./refs/frames/*.png)

    1. Extract one frame every 0.5 s:
       ffmpeg -i refs/launch.mp4 -vf "fps=2,scale=480:-1" refs/frames/%03d.png
       and a sheet: ffmpeg -i refs/launch.mp4 -vf "fps=2,scale=320:-1,tile=6x5" -frames:v 1 refs/sheet.png
       Study them.
    2. Write docs/style_guide.md: palette (hex), type (family, weight, tracking),
       shot lengths, transition types, camera moves, texture/grain, how text enters and exits.
    3. Write docs/shotlist.md for a [DURATION]s video about [SUBJECT] in THAT style.
       Take the grammar of the reference, never its content, logos or characters.
    4. Show me both files. Wait for my OK before any code.

A single frame works too: say what to take (palette, type, grain) and what not to take (subject).
Naming a style beats describing one ("Swiss poster", "Apple keynote product film", "PC-98 pixel art").
