"""Atlas packers — grid for icons, shelf packer for variable sizes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

ICON_SIZE = 24
ICON_ATLAS_SIZE = 2048
ICONS_PER_ROW = ICON_ATLAS_SIZE // ICON_SIZE
MAX_ATLAS_SIZE = 4096
WEBP_QUALITY = 80


@dataclass
class AtlasPage:
    page: int
    image: str
    mapping: str
    count: int
    width: int
    height: int


def pack_icon_atlases(
    unique_images: dict[str, Image.Image],
    id_to_key: dict[str, str],
    output_dir: Path,
) -> list[AtlasPage]:
    """Pack unique icon images; map every id to the shared rect of its key."""
    output_dir.mkdir(parents=True, exist_ok=True)
    keys = sorted(unique_images.keys())
    per_atlas = ICONS_PER_ROW * ICONS_PER_ROW
    pages: list[AtlasPage] = []

    # Precompute key → (page, x, y)
    key_rect: dict[str, tuple[int, int, int]] = {}
    for index, key in enumerate(keys):
        page = index // per_atlas
        local = index % per_atlas
        col = local % ICONS_PER_ROW
        row = local // ICONS_PER_ROW
        key_rect[key] = (page, col * ICON_SIZE, row * ICON_SIZE)

    page_count = (len(keys) + per_atlas - 1) // per_atlas if keys else 0
    for page in range(page_count):
        slice_keys = keys[page * per_atlas : (page + 1) * per_atlas]
        rows = max(1, (len(slice_keys) + ICONS_PER_ROW - 1) // ICONS_PER_ROW)
        height = rows * ICON_SIZE
        atlas = Image.new("RGBA", (ICON_ATLAS_SIZE, height), (0, 0, 0, 0))
        for i, key in enumerate(slice_keys):
            col = i % ICONS_PER_ROW
            row = i // ICONS_PER_ROW
            atlas.paste(unique_images[key], (col * ICON_SIZE, row * ICON_SIZE), unique_images[key])

        image_name = f"atlas_{page}.webp"
        mapping_name = f"atlas_{page}.json"
        atlas.save(output_dir / image_name, "WEBP", quality=WEBP_QUALITY, method=4)

        mapping: dict[str, dict] = {}
        for item_id, key in id_to_key.items():
            rect = key_rect.get(key)
            if not rect or rect[0] != page:
                continue
            _, x, y = rect
            mapping[item_id] = {"x": x, "y": y, "w": ICON_SIZE, "h": ICON_SIZE, "page": page}

        (output_dir / mapping_name).write_text(json.dumps(mapping, separators=(",", ":")), encoding="utf-8")
        pages.append(
            AtlasPage(
                page=page,
                image=image_name,
                mapping=mapping_name,
                count=len(mapping),
                width=ICON_ATLAS_SIZE,
                height=height,
            )
        )
    return pages


def pack_variable_atlases(
    unique_images: dict[str, Image.Image],
    id_to_key: dict[str, str],
    output_dir: Path,
    padding: int = 1,
    max_size: int = MAX_ATLAS_SIZE,
) -> list[AtlasPage]:
    """Shelf-pack unique images; expand id mapping onto shared rects."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if not unique_images:
        return []

    # Sort tallest-first for slightly better shelves
    remaining = sorted(
        unique_images.items(),
        key=lambda kv: (-kv[1].size[1], -kv[1].size[0], kv[0]),
    )
    pages: list[AtlasPage] = []
    page = 0
    key_rect: dict[str, tuple[int, int, int, int, int]] = {}  # key → page,x,y,w,h

    while remaining:
        atlas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
        x = padding
        y = padding
        shelf_h = 0
        used_w = padding
        used_h = padding
        placed: list[str] = []
        still: list[tuple[str, Image.Image]] = []

        for key, img in remaining:
            w, h = img.size
            if w + 2 * padding > max_size or h + 2 * padding > max_size:
                # skip oversized — should not happen after resize
                continue
            if x + w + padding > max_size:
                x = padding
                y += shelf_h + padding
                shelf_h = 0
            if y + h + padding > max_size:
                still.append((key, img))
                continue
            atlas.paste(img, (x, y), img)
            key_rect[key] = (page, x, y, w, h)
            placed.append(key)
            shelf_h = max(shelf_h, h)
            x += w + padding
            used_w = max(used_w, x)
            used_h = max(used_h, y + h + padding)

        if not placed:
            break

        crop_w = min(max_size, max(used_w, 1))
        crop_h = min(max_size, max(used_h, 1))
        cropped = atlas.crop((0, 0, crop_w, crop_h))
        image_name = f"atlas_{page}.webp"
        mapping_name = f"atlas_{page}.json"
        cropped.save(output_dir / image_name, "WEBP", quality=WEBP_QUALITY, method=4)

        mapping: dict[str, dict] = {}
        for item_id, key in id_to_key.items():
            rect = key_rect.get(key)
            if not rect or rect[0] != page:
                continue
            _, rx, ry, rw, rh = rect
            mapping[item_id] = {"x": rx, "y": ry, "w": rw, "h": rh, "page": page}

        (output_dir / mapping_name).write_text(json.dumps(mapping, separators=(",", ":")), encoding="utf-8")
        pages.append(
            AtlasPage(
                page=page,
                image=image_name,
                mapping=mapping_name,
                count=len(mapping),
                width=crop_w,
                height=crop_h,
            )
        )
        remaining = still
        page += 1

    return pages
