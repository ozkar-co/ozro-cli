#!/usr/bin/env python3
"""Render map previews for ozro-site.

Writes both textured minimaps (GRF) and walkable schematics (map_cache) when
available, so the site can toggle between them per map.

Coordinate math uses mapWidth/mapHeight from the GAT/cache cell grid.

Usage:
  python3 tools/build_map_images.py \
    --rathena /home/oz/Code/rathena \
    --maps ../ozro-site/assets/maps/all-maps.json \
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
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent
CLI_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from atlas.bmp import bmp_to_image  # noqa: E402
from atlas.grf_stack import GrfStack, default_grf_paths  # noqa: E402
from atlas.paths import map_minimap_candidates  # noqa: E402

HEADER = struct.Struct("<II")
INFO = struct.Struct("<12shhI")

COLORS = {
    0: (201, 194, 168),
    1: (90, 83, 72),
    2: (201, 194, 168),
    3: (90, 143, 176),
    4: (201, 194, 168),
    5: (138, 130, 114),
    6: (201, 194, 168),
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
        maps[map_name] = (xs, ys, data[pos : pos + length])
        pos += length
    return maps


def load_map_caches(root: str) -> dict[str, tuple[int, int, bytes]]:
    maps: dict[str, tuple[int, int, bytes]] = {}
    for rel in ("db/map_cache.dat", "db/re/map_cache.dat", "db/import/map_cache.dat"):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            maps.update(read_map_cache(path))
    return maps


def render_walkable(xs: int, ys: int, compressed: bytes) -> Image.Image | None:
    try:
        cells = zlib.decompress(compressed)
    except zlib.error:
        return None
    if len(cells) != xs * ys:
        return None

    flipped = b"".join(cells[(ys - 1 - y) * xs : (ys - y) * xs] for y in range(ys))
    image = Image.frombytes("P", (xs, ys), flipped)
    palette = []
    for index in range(256):
        palette.extend(COLORS.get(index & 0x7, (68, 68, 68)))
    image.putpalette(palette)
    return image.convert("RGB")


def load_minimap(stack: GrfStack, map_name: str) -> Image.Image | None:
    for path in map_minimap_candidates(map_name):
        raw = stack.read(path)
        if not raw:
            continue
        try:
            img = bmp_to_image(raw)
        except Exception:
            continue
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (32, 32, 32))
            bg.paste(img, mask=img.split()[3])
            return bg
        return img.convert("RGB")
    return None


def is_junk_minimap(image: Image.Image) -> bool:
    """Reject solid / near-solid placeholders (e.g. ama_in02 all gray)."""
    rgb = image.convert("RGB")
    # Sample a grid for speed
    w, h = rgb.size
    step = max(1, min(w, h) // 32)
    samples = [
        rgb.getpixel((x, y))
        for y in range(0, h, step)
        for x in range(0, w, step)
    ]
    if not samples:
        return True
    unique = len(set(samples))
    means = [(r + g + b) / 3 for r, g, b in samples]
    mean = sum(means) / len(means)
    var = sum((m - mean) ** 2 for m in means) / len(means)
    # Single (or tiny) palette and low variance = garbage textured "black" minimap
    if unique <= 4 and var < 100:
        return True
    if mean < 40 and var < 200:
        return True
    return False


def clear_webp_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    for stale in os.listdir(path):
        if stale.endswith(".webp"):
            os.remove(os.path.join(path, stale))


def save_webp(image: Image.Image, path: str) -> None:
    image.save(path, "WEBP", quality=82, method=4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rathena", default="/home/oz/Code/rathena")
    parser.add_argument(
        "--maps",
        default="../ozro-site/assets/maps/all-maps.json",
    )
    parser.add_argument("--out", default="../ozro-site/assets/maps")
    parser.add_argument("--cli-root", type=Path, default=CLI_ROOT)
    parser.add_argument("--client-dir", type=Path, default=None)
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="nearest-neighbor scale for walkable images",
    )
    parser.add_argument(
        "--prefer",
        choices=("minimap", "walkable"),
        default="walkable",
        help="Default source copied to images/ for thumbs (walkable is most reliable)",
    )
    args = parser.parse_args()

    with open(args.maps, "r", encoding="utf-8") as handle:
        spawn_index = json.load(handle)

    cache = load_map_caches(args.rathena)
    grf_paths = default_grf_paths(args.cli_root.resolve(), args.client_dir)
    if not grf_paths:
        print("warning: no GRFs found — minimaps unavailable", flush=True)
        stack = None
    else:
        print(
            f"GRF stack ({len(grf_paths)}): " + ", ".join(p.name for p in grf_paths),
            flush=True,
        )
        stack = GrfStack(grf_paths)

    images_dir = os.path.join(args.out, "images")
    minimap_dir = os.path.join(args.out, "minimap")
    walkable_dir = os.path.join(args.out, "walkable")
    clear_webp_dir(images_dir)
    clear_webp_dir(minimap_dir)
    clear_webp_dir(walkable_dir)

    index: dict[str, dict] = {}
    skipped: list[str] = []
    source_counts = {"minimap": 0, "walkable": 0, "both": 0}

    for entry in spawn_index.get("maps", []):
        map_name = entry["map"]
        source = cache.get(map_name) or cache.get(f"p{map_name}")
        xs = ys = None
        compressed = None
        if source is not None:
            xs, ys, compressed = source

        minimap_img = load_minimap(stack, map_name) if stack is not None else None
        if minimap_img is not None and is_junk_minimap(minimap_img):
            minimap_img = None

        walkable_img = None
        if xs is not None and compressed is not None:
            walkable_img = render_walkable(xs, ys, compressed)
            if walkable_img is not None and args.scale > 1:
                walkable_img = walkable_img.resize(
                    (xs * args.scale, ys * args.scale), Image.Resampling.NEAREST
                )

        if minimap_img is None and walkable_img is None:
            skipped.append(map_name)
            continue

        map_w = xs if xs is not None else (minimap_img or walkable_img).width
        map_h = ys if ys is not None else (minimap_img or walkable_img).height
        filename = f"{map_name}.webp"
        entry_out: dict = {
            "mapWidth": map_w,
            "mapHeight": map_h,
            "sources": [],
        }

        if minimap_img is not None:
            save_webp(minimap_img, os.path.join(minimap_dir, filename))
            entry_out["minimap"] = {
                "image": f"/assets/maps/minimap/{filename}",
                "width": minimap_img.width,
                "height": minimap_img.height,
            }
            entry_out["sources"].append("minimap")
            source_counts["minimap"] += 1

        if walkable_img is not None:
            save_webp(walkable_img, os.path.join(walkable_dir, filename))
            entry_out["walkable"] = {
                "image": f"/assets/maps/walkable/{filename}",
                "width": walkable_img.width,
                "height": walkable_img.height,
            }
            entry_out["sources"].append("walkable")
            source_counts["walkable"] += 1

        if minimap_img is not None and walkable_img is not None:
            source_counts["both"] += 1

        preferred = args.prefer
        if preferred not in entry_out["sources"]:
            preferred = entry_out["sources"][0]
        entry_out["defaultSource"] = preferred

        preferred_img = minimap_img if preferred == "minimap" else walkable_img
        assert preferred_img is not None
        save_webp(preferred_img, os.path.join(images_dir, filename))
        # Compat fields for thumbs / older readers
        entry_out["image"] = f"/assets/maps/images/{filename}"
        entry_out["width"] = preferred_img.width
        entry_out["height"] = preferred_img.height
        entry_out["source"] = preferred

        index[map_name] = entry_out

    payload = {
        "schemaVersion": 3,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "prefer": args.prefer,
        "sources": source_counts,
        "maps": index,
    }
    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    print(f"Mapas renderizados: {len(index)}")
    print(f"  con minimap:  {source_counts['minimap']}")
    print(f"  con walkable: {source_counts['walkable']}")
    print(f"  con ambos:    {source_counts['both']}")
    print(f"Sin datos:      {len(skipped)}")
    if skipped:
        print("  " + ", ".join(skipped[:20]) + (" ..." if len(skipped) > 20 else ""))
    print(f"Salida:         {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
