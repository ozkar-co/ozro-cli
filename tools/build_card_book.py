#!/usr/bin/env python3
"""Build the OzRo card-book atlas and catalog.

Inputs:
  - rAthena Card Collector NPC (source of CardBook categories/order)
  - rAthena item DB (card names)
  - GRF stack `data/num2cardillustnametable.txt` + `cardbmp/*.bmp`
    (preferred), or legacy `--mapping` + `--cardbmp-dir`

Outputs (default: ../ozro-site/assets/cards):
  - atlas_<n>.<hash>.webp
  - catalog.json  (categories for CardBook + byId for database modal)
  - build-report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent
CODE_ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NPC = CODE_ROOT / "rathena/npc/custom/ozro/card_collector.txt"
DEFAULT_ITEM_DB = CODE_ROOT / "rathena/db"
DEFAULT_MAPPING = Path(__file__).with_name("cardbmp-map.json")
DEFAULT_CARDBMP = Path("/tmp/cardbmp-all")
DEFAULT_OUT = CODE_ROOT / "ozro-site/assets/cards"
CARDBMP_DIR = "data/texture/유저인터페이스/cardbmp"
NUM2_TABLE = "data/num2cardillustnametable.txt"

CATEGORY_ORDER = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N",
    "O", "P", "Q", "R", "S", "T", "U", "V", "W", "Y", "Z", "BOSS", "MVP",
]

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def parse_categories(path: Path) -> list[tuple[str, list[int]]]:
    text = path.read_text(encoding="latin-1")
    result = []
    for code, body in re.findall(r"setarray \.card_arr_(\w+),\s*([0-9,\s]+);", text):
        result.append((code, [int(x) for x in re.findall(r"\d+", body)]))
    order = {code: index for index, code in enumerate(CATEGORY_ORDER)}
    result.sort(key=lambda item: order.get(item[0], 999))
    return result


def parse_item_names(db_root: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    for pattern in ("re/item_db_*.yml", "import/item_db*.yml"):
        for path in db_root.glob(pattern):
            current = None
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = re.match(r"\s*- Id: (\d+)", line)
                if match:
                    current = int(match.group(1))
                    continue
                if current is None:
                    continue
                match = re.match(r"\s+Name: (.+)", line)
                if match:
                    names[current] = match.group(1).strip()
    return names


def parse_num2_table(raw: bytes) -> dict[int, str]:
    text = raw.decode("cp949", errors="replace")
    out: dict[int, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        match = re.match(r"^(\d+)#([^#]*)#$", line)
        if not match:
            continue
        stem = match.group(2).strip()
        out[int(match.group(1))] = stem
    return out


def is_placeholder_stem(stem: str) -> bool:
    return not stem or stem.lower() == "sorry"


def page_group(code: str) -> int:
    return 1 if code in ("BOSS", "MVP") else 0


def save_hashed_webp(image: Image.Image, out_dir: Path, index: int, quality: int) -> str:
    temp = out_dir / f".atlas_{index}.tmp.webp"
    image.save(temp, "WEBP", quality=quality, method=6)
    digest = hashlib.sha1(temp.read_bytes()).hexdigest()[:10]
    filename = f"atlas_{index}.{digest}.webp"
    target = out_dir / filename
    temp.replace(target)
    return filename


def open_grf_stack(cli_root: Path):
    from atlas.grf_stack import GrfStack, default_grf_paths
    from atlas.bmp import bmp_to_image

    paths = default_grf_paths(cli_root)
    if not paths:
        raise SystemExit("No GRFs found for cardbmp extraction")
    stack = GrfStack(paths)
    return stack, bmp_to_image


def load_card_image_from_grf(stack, bmp_to_image, stem: str) -> Image.Image | None:
    if is_placeholder_stem(stem):
        return None
    raw = stack.read(f"{CARDBMP_DIR}/{stem}.bmp")
    if not raw:
        return None
    try:
        return bmp_to_image(raw).convert("RGB")
    except Exception:
        return None


def load_card_image_from_dir(cardbmp_dir: Path, filename: str) -> Image.Image | None:
    source = cardbmp_dir / filename
    if not source.is_file():
        # Allow stem without extension in mapping
        if not filename.lower().endswith(".bmp"):
            source = cardbmp_dir / f"{filename}.bmp"
        if not source.is_file():
            return None
    try:
        return Image.open(source).convert("RGB")
    except Exception:
        return None


def pack_pages(
    groups: dict[int, list[dict]],
    out_dir: Path,
    tile_w: int,
    tile_h: int,
    columns: int,
    quality: int,
) -> list[dict]:
    cell_w, cell_h = tile_w + 1, tile_h + 1
    pages: list[dict] = []

    for group in sorted(groups):
        page_cards = groups[group]
        if not page_cards:
            continue
        page_index = len(pages)
        cols = min(columns, len(page_cards))
        rows = math.ceil(len(page_cards) / cols)
        width, height = cols * cell_w, rows * cell_h
        atlas = Image.new("RGB", (width, height), (255, 255, 255))

        for position, card in enumerate(page_cards):
            image = card["_image"].resize((tile_w, tile_h), Image.LANCZOS)
            x = (position % cols) * cell_w
            y = (position // cols) * cell_h
            atlas.paste(image, (x, y))
            card["_rect"] = {"x": x, "y": y, "w": tile_w, "h": tile_h, "page": page_index}

        image_name = save_hashed_webp(atlas, out_dir, page_index, quality)
        pages.append(
            {
                "page": page_index,
                "image": image_name,
                "width": width,
                "height": height,
                "count": len(page_cards),
            }
        )
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Build card-book atlas and catalog")
    parser.add_argument("--npc", type=Path, default=DEFAULT_NPC)
    parser.add_argument("--item-db", type=Path, default=DEFAULT_ITEM_DB)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--cardbmp-dir", type=Path, default=DEFAULT_CARDBMP)
    parser.add_argument("--cli-root", type=Path, default=CLI_ROOT)
    parser.add_argument(
        "--from-grf",
        action="store_true",
        default=True,
        help="Read num2cardillustnametable + cardbmp from the GRF stack (default)",
    )
    parser.add_argument(
        "--from-dir",
        action="store_true",
        help="Use legacy --mapping + --cardbmp-dir instead of GRF",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tile-width", type=int, default=150)
    parser.add_argument("--tile-height", type=int, default=200)
    parser.add_argument("--columns", type=int, default=20)
    parser.add_argument("--quality", type=int, default=86)
    args = parser.parse_args()
    use_grf = not args.from_dir

    categories = parse_categories(args.npc)
    item_names = parse_item_names(args.item_db)

    stack = None
    bmp_to_image = None
    illust_table: dict[int, str] = {}
    file_mapping: dict[str, str] = {}

    if use_grf:
        stack, bmp_to_image = open_grf_stack(args.cli_root)
        raw = stack.read(NUM2_TABLE)
        if not raw:
            raise SystemExit(f"Missing {NUM2_TABLE} in GRF stack")
        illust_table = parse_num2_table(raw)
        print(f"GRF illust table: {len(illust_table)} ids")
    else:
        if not args.cardbmp_dir.is_dir():
            raise SystemExit(f"cardbmp directory not found: {args.cardbmp_dir}")
        if not args.mapping.is_file():
            raise SystemExit(f"mapping file not found: {args.mapping}")
        file_mapping = json.loads(args.mapping.read_text(encoding="utf-8"))

    def resolve_image(item_id: int) -> Image.Image | None:
        if use_grf:
            stem = illust_table.get(item_id)
            if stem is None:
                return None
            return load_card_image_from_grf(stack, bmp_to_image, stem)
        filename = file_mapping.get(str(item_id))
        if not filename:
            return None
        return load_card_image_from_dir(args.cardbmp_dir, filename)

    seen: set[int] = set()
    catalog_categories = []
    cards_by_page: dict[int, list[dict]] = {0: [], 1: [], 2: []}
    missing_mapping: list[int] = []
    missing_art: list[tuple[int, str]] = []
    placeholder_skip: list[int] = []
    all_cards: list[dict] = []

    for code, ids in categories:
        cards = []
        for item_id in ids:
            if item_id in seen:
                continue
            seen.add(item_id)
            if use_grf:
                stem = illust_table.get(item_id, "")
                if is_placeholder_stem(stem) and item_id in illust_table:
                    placeholder_skip.append(item_id)
                    missing_art.append((item_id, stem or "sorry"))
                    continue
                if item_id not in illust_table:
                    missing_mapping.append(item_id)
                    continue
            image = resolve_image(item_id)
            if image is None:
                label = illust_table.get(item_id) if use_grf else file_mapping.get(str(item_id), "?")
                missing_art.append((item_id, str(label)))
                continue
            name = item_names.get(item_id, f"Item {item_id}")
            card = {
                "id": item_id,
                "name": name,
                "_image": image,
                "_category": code,
            }
            cards.append(card)
            all_cards.append(card)
            cards_by_page[page_group(code)].append(card)
        cards.sort(key=lambda card: (card["name"].casefold(), card["id"]))
        catalog_categories.append({"code": code, "label": code, "cards": cards})

    # Pack every other card with real client art so ItemCard can open them.
    extras: list[dict] = []
    if use_grf:
        for item_id, stem in sorted(illust_table.items()):
            if item_id in seen:
                continue
            if is_placeholder_stem(stem):
                placeholder_skip.append(item_id)
                continue
            image = load_card_image_from_grf(stack, bmp_to_image, stem)
            if image is None:
                missing_art.append((item_id, stem))
                continue
            seen.add(item_id)
            name = item_names.get(item_id, f"Item {item_id}")
            card = {
                "id": item_id,
                "name": name,
                "_image": image,
                "_category": "EXTRA",
            }
            extras.append(card)
            all_cards.append(card)
        extras.sort(key=lambda card: (card["name"].casefold(), card["id"]))
        if extras:
            cards_by_page[2].extend(extras)

    if missing_mapping and not use_grf:
        raise SystemExit(f"cards without a cardbmp mapping: {missing_mapping}")
    if missing_art and not use_grf:
        raise SystemExit(f"cardbmp files not found: {missing_art}")

    if missing_mapping:
        print(f"warning: collector cards missing num2 entry: {len(missing_mapping)}")
    if missing_art:
        print(f"warning: cards without cardbmp file: {len(missing_art)}")
    if placeholder_skip:
        print(f"skipped placeholder/sorry art: {len(placeholder_skip)}")

    args.out.mkdir(parents=True, exist_ok=True)
    for stale in args.out.glob("atlas_*.webp"):
        stale.unlink()

    pages = pack_pages(
        cards_by_page,
        args.out,
        args.tile_width,
        args.tile_height,
        args.columns,
        args.quality,
    )

    by_id: dict[str, dict] = {}
    for card in all_cards:
        rect = card["_rect"]
        by_id[str(card["id"])] = {
            "id": card["id"],
            "name": card["name"],
            "page": rect["page"],
            "x": rect["x"],
            "y": rect["y"],
            "w": rect["w"],
            "h": rect["h"],
        }

    catalog = {
        "version": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "total": len(by_id),
        "cardWidth": args.tile_width,
        "cardHeight": args.tile_height,
        "pages": pages,
        "categories": [],
        "byId": by_id,
    }

    for category in catalog_categories:
        output_cards = []
        for card in category["cards"]:
            rect = card["_rect"]
            output_cards.append(
                {
                    "id": card["id"],
                    "name": card["name"],
                    "page": rect["page"],
                    "x": rect["x"],
                    "y": rect["y"],
                    "w": rect["w"],
                    "h": rect["h"],
                }
            )
        catalog["categories"].append(
            {
                "code": category["code"],
                "label": category["label"],
                "cards": output_cards,
            }
        )

    (args.out / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = {
        "generatedAt": catalog["generatedAt"],
        "total": catalog["total"],
        "collectorCards": sum(len(c["cards"]) for c in catalog["categories"]),
        "extraCards": len(extras),
        "placeholderSkipped": len(set(placeholder_skip)),
        "missingMapping": missing_mapping[:50],
        "missingArt": missing_art[:50],
        "pages": pages,
        "categories": [
            {"code": category["code"], "total": len(category["cards"])}
            for category in catalog["categories"]
        ],
        "source": {
            "mode": "grf" if use_grf else "dir",
            "npc": str(args.npc),
            "itemDb": str(args.item_db),
            "mapping": str(args.mapping) if not use_grf else NUM2_TABLE,
            "cardbmpDir": str(args.cardbmp_dir) if not use_grf else CARDBMP_DIR,
        },
    }
    (args.out / "build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Keep legacy map in sync for tooling that still reads it.
    if use_grf:
        legacy = {
            str(item_id): f"{stem}.bmp"
            for item_id, stem in sorted(illust_table.items())
            if not is_placeholder_stem(stem) and str(item_id) in by_id
        }
        DEFAULT_MAPPING.write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(f"cards: {catalog['total']} (collector {report['collectorCards']}, extra {report['extraCards']})")
    print(f"pages: {len(pages)}")
    for page in pages:
        print(
            f"  page {page['page']}: {page['count']} cards, "
            f"{page['width']}x{page['height']}, {page['image']}"
        )
    print(f"output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
