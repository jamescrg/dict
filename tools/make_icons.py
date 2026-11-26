#!/usr/bin/env python3
"""Draw the home-screen icons (the open book of favicon.svg, with room around it
for a maskable crop) into lookup/static/lookup/.

Usage: uv run --with pillow tools/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "lookup/static/lookup"
# The launcher icon's pages, on its 108-unit canvas (dict-android, ic_launcher_foreground.xml).
PAGES = [("#ebdbb2", [(31, 39), (52, 45), (52, 74), (31, 68)]),
         ("#fabd2f", [(77, 39), (56, 45), (56, 74), (77, 68)])]
VIEW = (18, 18, 90, 90)  # the part of that canvas an icon shows

for size in (180, 192, 512):
    big = size * 4
    image = Image.new("RGB", (big, big), "#282828")
    draw = ImageDraw.Draw(image)
    scale = big / (VIEW[2] - VIEW[0])
    for colour, points in PAGES:
        draw.polygon([((x - VIEW[0]) * scale, (y - VIEW[1]) * scale) for x, y in points], fill=colour)
    image.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png", optimize=True)
    print(OUT / f"icon-{size}.png")
