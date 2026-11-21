#!/usr/bin/env python3
"""Export machine-readable client asset inventory (JSONL + meta).

Reads data.ini priority (first wins). Writes reports under --out-dir:

  client_grf_index_meta.json
  client_maps.jsonl
  client_item_icons.jsonl
  client_item_sprites.jsonl
  client_item_info.jsonl      # from System/itemInfo_EN.lua when present
  client_mob_sprites.jsonl
  client_npc_sprites.jsonl

Example:
  python3 tools/export_client_inventory.py \\
      --cli-root . --out-dir ../ozro-data/reports
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grf import Grf, GrfError  # noqa: E402

SCHEMA_VERSION = 1

ITEM_INFO_CANDIDATES = (
    "patch/System/itemInfo_EN.lua",
    "System/itemInfo_EN.lua",
)


def norm_path(p: str) -> str:
    return p.replace("\\", "/").lower()


def basename(p: str) -> str:
    return p.rsplit("/", 1)[-1]


def stem_of(p: str) -> str:
    b = basename(p)
    return b.rsplit(".", 1)[0] if "." in b else b


def ext_of(p: str) -> str:
    b = basename(p)
    return b.rsplit(".", 1)[-1].lower() if "." in b else ""


def parse_data_ini(path: Path) -> list[str]:
    order: list[tuple[int, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("[") or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        try:
            order.append((int(k.strip()), v.strip()))
        except ValueError:
            continue
    order.sort(key=lambda t: t[0])
    return [name for _, name in order]


def sha256_file(path: Path, limit: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        if limit is None:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        else:
            h.update(f.read(limit))
            h.update(f"\0size={path.stat().st_size}".encode())
    return h.hexdigest()


def resolve_grf(cli_root: Path, name: str) -> Path:
    for candidate in (cli_root / "patch" / name, cli_root / "tmp" / name, cli_root / name):
        if candidate.is_file():
            return candidate
    raise GrfError(f"GRF not found for {name}: tried patch/, tmp/, root")


def label_of(name: str) -> str:
    return Path(name).stem


def build_index(cli_root: Path, ini_order: list[str]) -> tuple[dict, dict, list[dict]]:
    """Return (active[path_norm]->(label, orig_name), by_label counts, grf_meta list)."""
    active: dict[str, tuple[str, str]] = {}
    grf_meta: list[dict] = []
    for prio, name in enumerate(ini_order, start=1):
        path = resolve_grf(cli_root, name)
        label = label_of(name)
        print(f"indexing [{prio}] {label}: {path}", flush=True)
        grf = Grf(path)
        added = 0
        for e in grf.entries:
            key = norm_path(e.name)
            if key in active:
                continue
            active[key] = (label, e.name)
            added += 1
        grf_meta.append(
            {
                "priority": prio,
                "label": label,
                "file": name,
                "path": str(path.relative_to(cli_root)),
                "entries": grf.count,
                "winners_contributed": added,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return active, grf_meta


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def parse_resnametable(data: bytes) -> dict[str, dict[str, str]]:
    """Parse data/resnametable.txt → alias_stem → {ext: target_stem}.

    Lines look like: airplane_01.rsw#airplane.rsw#
    """
    text = data.decode("cp949", errors="replace")
    out: dict[str, dict[str, str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        parts = [p for p in line.split("#") if p]
        if len(parts) < 2:
            continue
        src, dst = parts[0].strip(), parts[1].strip()
        src_ext, dst_ext = ext_of(src), ext_of(dst)
        if src_ext not in {"rsw", "gat", "gnd"}:
            continue
        if dst_ext and dst_ext != src_ext:
            continue
        alias = stem_of(src).lower()
        target = stem_of(dst).lower()
        if not alias or not target or alias == target:
            continue
        out.setdefault(alias, {})[src_ext] = target
    return out


def read_active_file(
    active: dict[str, tuple[str, str]],
    grfs: dict[str, Grf],
    key: str,
) -> bytes | None:
    hit = active.get(norm_path(key))
    if not hit:
        return None
    label, orig = hit
    grf = grfs.get(label)
    if grf is None:
        return None
    try:
        return grf.read(grf.find(orig))
    except GrfError:
        return None


def export_maps(
    active: dict[str, tuple[str, str]],
    grfs: dict[str, Grf] | None = None,
) -> list[dict]:
    rsw: dict[str, str] = {}
    gat: dict[str, str] = {}
    gnd: dict[str, str] = {}
    minimaps: set[str] = set()

    for key, (label, _orig) in active.items():
        if not key.startswith("data/"):
            continue
        # maps live as data/<stem>.{rsw,gat,gnd}
        parts = key.split("/")
        if len(parts) == 2:
            st, ext = stem_of(parts[1]), ext_of(parts[1])
            if ext == "rsw":
                rsw[st] = label
            elif ext == "gat":
                gat[st] = label
            elif ext == "gnd":
                gnd[st] = label
        if "/map/" in key and ext_of(key) in ("bmp", "tga", "png", "jpg"):
            minimaps.add(stem_of(key).lower())

    aliases: dict[str, dict[str, str]] = {}
    if grfs:
        raw = read_active_file(active, grfs, "data/resnametable.txt")
        if raw:
            aliases = parse_resnametable(raw)

    physical = set(rsw) | set(gat) | set(gnd)
    maps = sorted(physical | set(aliases), key=lambda s: s.lower())
    rows = []
    for mid in maps:
        alias = aliases.get(mid.lower(), {})
        resolved: dict[str, str] = {}
        winners: dict[str, str] = {}
        via_alias: dict[str, str] = {}

        for ext, bucket in (("rsw", rsw), ("gat", gat), ("gnd", gnd)):
            if mid in bucket:
                resolved[ext] = mid
                winners[ext] = bucket[mid]
            elif ext in alias and alias[ext] in bucket:
                target = alias[ext]
                resolved[ext] = target
                winners[ext] = bucket[target]
                via_alias[ext] = target

        has_rsw = "rsw" in resolved
        has_gat = "gat" in resolved
        has_gnd = "gnd" in resolved
        row = {
            "map_id": mid,
            "has_rsw": has_rsw,
            "has_gat": has_gat,
            "has_gnd": has_gnd,
            "complete": has_rsw and has_gat and has_gnd,
            "winner_grf": winners,
            "minimap_present": mid.lower() in minimaps
            or any(t.lower() in minimaps for t in via_alias.values()),
        }
        if via_alias:
            row["alias_of"] = via_alias
            row["physical"] = mid in physical and mid in rsw and mid in gat and mid in gnd
        else:
            row["physical"] = has_rsw and has_gat and has_gnd
        rows.append(row)
    return rows


def _ui_folder_stems(
    active: dict[str, tuple[str, str]], folder: str, exts: set[str]
) -> dict[str, tuple[str, str]]:
    """stem -> (winner_label, original_path) for …/{folder}/*."""
    out: dict[str, tuple[str, str]] = {}
    needle = f"/{folder}/"
    for key, (label, orig) in active.items():
        if needle not in key:
            continue
        if ext_of(key) not in exts:
            continue
        # only direct children of the folder (not nested junk)
        # path …/folder/name.ext
        idx = key.rfind(needle)
        rest = key[idx + len(needle) :]
        if "/" in rest:
            continue
        st = stem_of(key)
        # keep first = already winner in active
        out[st] = (label, orig.replace("\\", "/"))
    return out


def export_item_icons(active: dict[str, tuple[str, str]]) -> list[dict]:
    items = _ui_folder_stems(active, "item", {"bmp", "tga", "png"})
    # also data/texture/item/ without UI path
    for key, (label, orig) in active.items():
        if key.startswith("data/texture/item/") and ext_of(key) in {"bmp", "tga", "png"}:
            if "/" in key[len("data/texture/item/") :]:
                continue
            st = stem_of(key)
            items.setdefault(st, (label, orig.replace("\\", "/")))

    collections = _ui_folder_stems(active, "collection", {"bmp", "tga", "png"})
    for key, (label, orig) in active.items():
        if key.startswith("data/texture/collection/") and ext_of(key) in {
            "bmp",
            "tga",
            "png",
        }:
            if "/" in key[len("data/texture/collection/") :]:
                continue
            st = stem_of(key)
            collections.setdefault(st, (label, orig.replace("\\", "/")))

    stems = sorted(set(items) | set(collections), key=lambda s: s.lower())
    rows = []
    for st in stems:
        paths: dict[str, str] = {}
        winners: dict[str, str] = {}
        if st in items:
            paths["item"] = items[st][1]
            winners["item"] = items[st][0]
        if st in collections:
            paths["collection"] = collections[st][1]
            winners["collection"] = collections[st][0]
        rows.append(
            {
                "resource_name": st,
                "has_item": st in items,
                "has_collection": st in collections,
                "paths": paths,
                "winner_grf": winners,
            }
        )
    return rows


def export_sprite_dir(
    active: dict[str, tuple[str, str]], folder_names: set[str]
) -> list[dict]:
    """sprite stems under data/sprite/<folder>/ with spr/act."""
    stems: dict[str, dict] = {}
    folders_l = {f.lower() for f in folder_names}
    for key, (label, orig) in active.items():
        if not key.startswith("data/sprite/"):
            continue
        parts = key.split("/")
        if len(parts) < 4:
            # data/sprite/file.spr — skip loose
            continue
        if parts[2] not in folders_l:
            continue
        # only files directly in folder or one subdir? mobs/npcs are flat; items flat
        # allow exactly data/sprite/<folder>/<file>
        if len(parts) != 4:
            continue
        ext = ext_of(key)
        if ext not in {"spr", "act"}:
            continue
        st = stem_of(key)
        slot = stems.setdefault(
            st,
            {
                "sprite_stem": st,
                "has_spr": False,
                "has_act": False,
                "winner_grf": {},
                "paths": {},
            },
        )
        slot[f"has_{ext}"] = True
        slot["winner_grf"][ext] = label
        slot["paths"][ext] = orig.replace("\\", "/")
    rows = []
    for st in sorted(stems.keys(), key=lambda s: s.lower()):
        row = stems[st]
        # flatten winner to single if same, else keep per-ext
        wg = row["winner_grf"]
        if len(set(wg.values())) == 1:
            row["winner_grf"] = next(iter(wg.values()))
        rows.append(row)
    return rows


def parse_item_info(path: Path) -> list[dict]:
    """Parse itemInfo_EN.lua (CP949) for id ↔ resource names."""
    raw = path.read_bytes()
    text = raw.decode("cp949", errors="replace")
    rows: list[dict] = []
    # Split on [id] = { blocks — robust enough for standard itemInfo
    block_re = re.compile(
        r"\[(\d+)\]\s*=\s*\{(.*?)\r?\n\t\},",
        re.S,
    )
    for m in block_re.finditer(text):
        item_id = int(m.group(1))
        body = m.group(2)

        def field_str(name: str) -> str | None:
            mm = re.search(rf'{name}\s*=\s*"((?:\\.|[^"\\])*)"', body)
            return mm.group(1) if mm else None

        def field_int(name: str) -> int | None:
            mm = re.search(rf"{name}\s*=\s*(-?\d+)", body)
            return int(mm.group(1)) if mm else None

        rows.append(
            {
                "item_id": item_id,
                "identified_resource_name": field_str("identifiedResourceName"),
                "unidentified_resource_name": field_str("unidentifiedResourceName"),
                "slot_count": field_int("slotCount"),
                "class_num": field_int("ClassNum"),
            }
        )
    return rows


def enrich_item_info(
    info_rows: list[dict],
    icons: list[dict],
    sprites: list[dict],
) -> list[dict]:
    icon_by = {r["resource_name"]: r for r in icons}
    spr_by = {r["sprite_stem"]: r for r in sprites}
    out = []
    for row in info_rows:
        ident = row.get("identified_resource_name") or ""
        unid = row.get("unidentified_resource_name") or ""
        icon = icon_by.get(ident)
        spr = spr_by.get(ident)
        enriched = dict(row)
        enriched["has_item_icon"] = bool(icon and icon.get("has_item"))
        enriched["has_collection"] = bool(icon and icon.get("has_collection"))
        enriched["has_sprite"] = bool(spr and spr.get("has_spr") and spr.get("has_act"))
        if unid and unid != ident:
            u_icon = icon_by.get(unid)
            u_spr = spr_by.get(unid)
            enriched["unidentified_has_item_icon"] = bool(
                u_icon and u_icon.get("has_item")
            )
            enriched["unidentified_has_sprite"] = bool(
                u_spr and u_spr.get("has_spr") and u_spr.get("has_act")
            )
        out.append(enriched)
    return out


def find_item_info(cli_root: Path) -> Path | None:
    for rel in ITEM_INFO_CANDIDATES:
        p = cli_root / rel
        if p.is_file():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cli-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="default: <cli-root>/../ozro-data/reports",
    )
    ap.add_argument(
        "--data-ini",
        type=Path,
        default=None,
        help="default: <cli-root>/patch/data.ini",
    )
    args = ap.parse_args()
    cli_root: Path = args.cli_root.resolve()
    out_dir: Path = (
        args.out_dir.resolve()
        if args.out_dir
        else (cli_root.parent / "ozro-data" / "reports").resolve()
    )
    ini_path: Path = (
        args.data_ini.resolve()
        if args.data_ini
        else (cli_root / "patch" / "data.ini")
    )

    try:
        ini_order = parse_data_ini(ini_path)
        if not ini_order:
            raise GrfError(f"no GRF entries in {ini_path}")
        active, grf_meta = build_index(cli_root, ini_order)
        grfs = {m["label"]: Grf(cli_root / m["path"]) for m in grf_meta}

        print("exporting maps…", flush=True)
        maps = export_maps(active, grfs)
        print("exporting item icons…", flush=True)
        icons = export_item_icons(active)
        print("exporting item sprites…", flush=True)
        item_spr = export_sprite_dir(active, {"아이템"})
        print("exporting mob sprites…", flush=True)
        mob_spr = export_sprite_dir(active, {"몬스터", "monster"})
        print("exporting npc sprites…", flush=True)
        npc_spr = export_sprite_dir(active, {"npc", "엔피씨"})

        item_info_path = find_item_info(cli_root)
        item_info: list[dict] = []
        if item_info_path:
            print(f"parsing itemInfo: {item_info_path}", flush=True)
            item_info = enrich_item_info(
                parse_item_info(item_info_path), icons, item_spr
            )

        out_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(out_dir / "client_maps.jsonl", maps)
        write_jsonl(out_dir / "client_item_icons.jsonl", icons)
        write_jsonl(out_dir / "client_item_sprites.jsonl", item_spr)
        write_jsonl(out_dir / "client_mob_sprites.jsonl", mob_spr)
        write_jsonl(out_dir / "client_npc_sprites.jsonl", npc_spr)
        if item_info:
            write_jsonl(out_dir / "client_item_info.jsonl", item_info)

        maps_alias = sum(1 for r in maps if r.get("alias_of"))
        maps_alias_complete = sum(
            1 for r in maps if r.get("alias_of") and r["complete"]
        )
        meta = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_ini": str(ini_path.relative_to(cli_root)),
            "data_ini_order": ini_order,
            "grf_paths": {m["label"]: m["path"] for m in grf_meta},
            "grfs": grf_meta,
            "active_path_count": len(active),
            "counts": {
                "maps": len(maps),
                "maps_complete": sum(1 for r in maps if r["complete"]),
                "maps_alias": maps_alias,
                "maps_alias_complete": maps_alias_complete,
                "item_icons": len(icons),
                "item_sprites": len(item_spr),
                "item_info": len(item_info),
                "mob_sprites": len(mob_spr),
                "npc_sprites": len(npc_spr),
            },
            "outputs": [
                "client_grf_index_meta.json",
                "client_maps.jsonl",
                "client_item_icons.jsonl",
                "client_item_sprites.jsonl",
                "client_item_info.jsonl" if item_info else None,
                "client_mob_sprites.jsonl",
                "client_npc_sprites.jsonl",
            ],
        }
        meta["outputs"] = [x for x in meta["outputs"] if x]
        (out_dir / "client_grf_index_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(meta["counts"], indent=2))
        print(f"wrote → {out_dir}")
    except (GrfError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
