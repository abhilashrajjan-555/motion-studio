#!/usr/bin/env bash
# Pack the skill folder into dist/motion-reel.zip for upload to Claude.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist && rm -f dist/motion-reel.zip
python3 - <<'PY'
import os, zipfile
with zipfile.ZipFile('dist/motion-reel.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('motion-reel'):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.pyc'):
                z.write(os.path.join(root, f))
PY
echo "dist/motion-reel.zip ($(du -h dist/motion-reel.zip | cut -f1))"
