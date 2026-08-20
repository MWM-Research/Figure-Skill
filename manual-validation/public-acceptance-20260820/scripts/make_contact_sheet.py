#!/usr/bin/env python3
"""Create a compact visual QA sheet for all public acceptance outputs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ITEMS = (
    ("Data plot", ROOT / "outputs" / "data-plot" / "final" / "figure.png"),
    ("Illustration", ROOT / "outputs" / "illustration" / "final" / "figure.png"),
    ("Composite", ROOT / "outputs" / "composite" / "final" / "figure.png"),
    ("Native SVG edit", ROOT / "outputs" / "edit" / "final" / "figure.png"),
    ("Artificial neuron reconstruction", ROOT / "outputs" / "reconstruction-artificial-neuron-retry-gemini" / "final-preview.png"),
    ("Neural network reconstruction", ROOT / "outputs" / "reconstruction-neural-network-ground-truth-retry-gemini" / "final-preview.png"),
)


def main() -> int:
    cell_width, cell_height, label_height = 640, 380, 34
    canvas = Image.new("RGB", (cell_width * 2, (cell_height + label_height) * 3), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    for index, (label, path) in enumerate(ITEMS):
        with Image.open(path) as image:
            converted = image.convert("RGB")
            converted.thumbnail((cell_width - 20, cell_height - 20), Image.Resampling.LANCZOS)
            row, column = divmod(index, 2)
            x = column * cell_width + (cell_width - converted.width) // 2
            y = row * (cell_height + label_height) + label_height + (cell_height - converted.height) // 2
            canvas.paste(converted, (x, y))
            draw.text((column * cell_width + 12, row * (cell_height + label_height) + 8), label, fill="black", font=font)
    output = ROOT / "reports" / "visual-qa-contact-sheet.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
