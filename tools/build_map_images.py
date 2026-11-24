#!/usr/bin/env python3
"""Render simple map previews from the rAthena map cache.

The client minimaps are encrypted in the current data.grf, so this tool uses
the map cache that the server already ships. It renders walkable cells as a
small WebP and writes assets/maps/index.json for the map viewer.

Usage:
  python3 tools/build_map_images.py \
    --rathena /home/oz/Code/rathena \
    --maps ../ozro-site/assets/spawns/maps.json \
    --out ../ozro-site/assets/maps
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib
from datetime import datetime, timezone

from PIL import Image

HEADER = struct.Struct("<II")
INFO = struct.Struct("<12shhI")

COLORS = {
    0: (201, 194, 168),  # walkable ground
    1: (90, 83, 72),     # non-walkable
    2: (201, 194, 168),  # walkable
    3: (90, 143, 176),   # water
    4: (201, 194, 168),  # walkable
    5: (138, 130, 114),  # gap / shootable
    6: (201, 194, 168),  # walkable
}


def read_map_cache(path: str) -> dict[str, tuple[int, int, bytes]]:
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) < HEADER.size:
        return {}
    _, count = HEADER.unpack_from(data, 0)
    pos = HEADER.size
    maps: dict[str, tuple[int, int, bytes]] = {}
    for _ in range(count):
        if pos + INFO.size > len(data):
            break
        name, xs, ys, length = INFO.unpack_from(data, pos)
        map_name = name.split(b"\0", 1)[0].decode("latin1")
        pos += INFO.size
        if xs <= 0 or ys <= 0 or pos + length > len(data):
            pos += length
            continue
        maps[map_name] = (xs, ys, data[pos:pos + length])
        pos += length
    return maps


def load_map_caches(root: str) -> dict[str, tuple[int, int, bytes]]:
    maps: dict[str, tuple[int, int, bytes]] = {}
    for rel in ("db/map_cache.dat", "db/re/map_cache.dat", "db/import/map_cache.dat"):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            maps.update(read_map_cache(path))
    return maps


def render_map(xs: int, ys: int, compressed: bytes) -> Image.Image | None:
    try:
        cells = zlib.decompress(compressed)
    except zlib.error:
        return None
    if len(cells) != xs * ys:
        return None

    flipped = b"".join(
        cells[(ys - 1 - y) * xs:(ys - y) * xs] for y in range(ys)
    )

    image = Image.frombytes("P", (xs, ys), flipped)
    palette = []
    for index in range(256):
        palette.extend(COLORS.get(index & 0x7, (68, 68, 68)))
    image.putpalette(palette)
    return image.convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rathena", default="/home/oz/Code/rathena", help="rAthena root")
    parser.add_argument("--maps", default="../ozro-site/assets/spawns/maps.json", help="spawn map index")
    parser.add_argument(
        "--out",
        default="../ozro-site/assets/maps",
        help="output asset directory (ozro-site)",
    )
    parser.add_argument("--scale", type=int, default=1, help="nearest-neighbor scale")
    args = parser.parse_args()

    with open(args.maps, "r", encoding="utf-8") as handle:
        spawn_index = json.load(handle)

    cache = load_map_caches(args.rathena)
    images_dir = os.path.join(args.out, "images")
    os.makedirs(images_dir, exist_ok=True)
    for stale in os.listdir(images_dir):
        if stale.endswith(".webp"):
            os.remove(os.path.join(images_dir, stale))

    index: dict[str, dict] = {}
    skipped: list[str] = []

    for entry in spawn_index.get("maps", []):
        map_name = entry["map"]
        source = cache.get(map_name) or cache.get(f"p{map_name}")
        if source is None:
            skipped.append(map_name)
            continue

        xs, ys, compressed = source
        image = render_map(xs, ys, compressed)
        if image is None:
            skipped.append(map_name)
            continue

        if args.scale > 1:
            image = image.resize((xs * args.scale, ys * args.scale), Image.Resampling.NEAREST)

        filename = f"{map_name}.webp"
        image.save(os.path.join(images_dir, filename), "WEBP", lossless=True, quality=100)
        index[map_name] = {
            "image": f"/assets/maps/images/{filename}",
            "width": image.width,
            "height": image.height,
            "mapWidth": xs,
            "mapHeight": ys,
        }

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "maps": index,
    }
    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    print(f"Mapas renderizados: {len(index)}")
    print(f"Sin datos de mapa:  {len(skipped)}")
    if skipped:
        print("  " + ", ".join(skipped[:20]) + (" ..." if len(skipped) > 20 else ""))
    print(f"Salida:             {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
