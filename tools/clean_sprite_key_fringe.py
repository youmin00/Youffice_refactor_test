"""Remove chroma-key residue from transparent pixel sprites.

Only magenta/purple or green pixels immediately next to already-transparent
pixels are removed.  Normal blue hair, black outlines, skin, and internal
drawing colors remain untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageFilter


def _looks_like_key_residue(red: int, green: int, blue: int) -> bool:
    """Identify leftover #ff00ff or #00ff00 key-color edge pixels."""

    magenta_residue = (
        red >= 50
        and blue >= 50
        and green <= min(red, blue) * 0.58
        and red + blue - 2 * green >= 95
    )
    green_residue = (
        green >= 50
        and red <= green * 0.58
        and blue <= green * 0.58
        and 2 * green - red - blue >= 95
    )
    return magenta_residue or green_residue


def clean_file(path: Path, radius: int = 2) -> int:
    with Image.open(path) as source:
        image = source.convert("RGBA")

    alpha = image.getchannel("A")
    transparent = alpha.point(lambda value: 255 if value == 0 else 0)
    near_transparent = transparent.filter(ImageFilter.MaxFilter(radius * 2 + 1))

    pixels = bytearray(image.tobytes())
    edge_mask = near_transparent.tobytes()
    removed = 0
    for pixel_index, is_near_transparent in enumerate(edge_mask):
        if not is_near_transparent:
            continue
        offset = pixel_index * 4
        red, green, blue, alpha_value = pixels[offset : offset + 4]
        if alpha_value and _looks_like_key_residue(red, green, blue):
            pixels[offset : offset + 4] = b"\x00\x00\x00\x00"
            removed += 1

    if removed:
        cleaned = Image.frombytes("RGBA", image.size, bytes(pixels))
        cleaned.save(path, optimize=True)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--radius", type=int, default=2)
    args = parser.parse_args()

    if args.radius < 1 or args.radius > 4:
        parser.error("--radius must be between 1 and 4")

    files = sorted(args.directory.rglob("*_source_alpha.png"))
    if not files:
        parser.error("No *_source_alpha.png files found")

    total_removed = 0
    for path in files:
        removed = clean_file(path, args.radius)
        total_removed += removed
        print(f"{path}: removed={removed}")
    print(f"cleaned: {len(files)} files, removed={total_removed} fringe pixels")


if __name__ == "__main__":
    main()
