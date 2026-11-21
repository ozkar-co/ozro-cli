#!/usr/bin/env python3
"""Export machine-readable client asset inventory (JSONL + meta).

Reads data.ini priority (first wins). Writes reports under --out-dir:

  client_grf_index_meta.json
  client_maps.jsonl            # + display_name, width, height (mapnametable + GAT)
  client_item_icons.jsonl
  client_item_sprites.jsonl
  client_item_info.jsonl      # from System/itemInfo_EN.lua when present
  client_item_server_gaps.jsonl  # server items missing itemInfo or assets
  client_mob_sprites.jsonl
  client_mob_server_gaps.jsonl   # server mobs missing identity/jobname/sprite
  client_mob_act_gaps.jsonl      # mob ACT→wav refs missing from client stack
  client_npc_sprites.jsonl
  client_npc_act_gaps.jsonl      # npc ACT→wav refs missing from client stack
  client_skills.jsonl            # skillid + skillinfolist + icon/sprite
  client_skill_server_gaps.jsonl # server skills missing client info/icon

Example:
  python3 tools/export_client_inventory.py \\
      --cli-root . --out-dir ../ozro-data/reports --rathena ../rathena
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grf import Grf, GrfError  # noqa: E402

SCHEMA_VERSION = 9

# ACT sound events store null-terminated filenames (may include spaces).
_WAV_NULL_TERM_RE = re.compile(
    rb"([A-Za-z0-9_][A-Za-z0-9_\- ]{0,63}\.wav)\x00", re.I
)

ITEM_INFO_CANDIDATES = (
    "patch/System/itemInfo_EN.lua",
    "System/itemInfo_EN.lua",
)

SERVER_ITEM_DB_FILES = (
    "db/re/item_db.yml",
    "db/re/item_db_equip.yml",
    "db/re/item_db_etc.yml",
    "db/re/item_db_usable.yml",
    "db/import/item_db.yml",
)

SERVER_MOB_DB_FILES = (
    "db/re/mob_db.yml",
    "db/import/mob_db.yml",
)

NPCIDENTITY_CANDIDATES = (
    "data/luafiles514/lua files/datainfo/npcidentity.lub",
    "data/lua files/datainfo/npcidentity.lub",
)

JOBNAME_CANDIDATES = (
    "data/luafiles514/lua files/datainfo/jobname.lub",
    "data/lua files/datainfo/jobname.lub",
)

SKILLID_CANDIDATES = (
    "data/luafiles514/lua files/skillinfoz/skillid.lub",
    "data/lua files/skillinfoz/skillid.lub",
)

SKILLINFOLIST_CANDIDATES = (
    "data/luafiles514/lua files/skillinfoz/skillinfolist.lub",
    "data/lua files/skillinfoz/skillinfolist.lub",
)

SKILLDESCRIPT_CANDIDATES = (
    "data/luafiles514/lua files/skillinfoz/skilldescript.lub",
    "data/lua files/skillinfoz/skilldescript.lub",
)

SERVER_SKILL_DB_FILES = (
    "db/re/skill_db.yml",
    "db/import/skill_db.yml",
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


def parse_mapnametable(data: bytes) -> dict[str, str]:
    """Parse data/mapnametable.txt → map_id → display_name.

    Lines look like: prontera.rsw#Prontera City#
    """
    text = data.decode("cp949", errors="replace")
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        parts = [p for p in line.split("#") if p]
        if len(parts) < 2:
            continue
        src, name = parts[0].strip(), parts[1].strip()
        if ext_of(src) != "rsw" or not name:
            continue
        out[stem_of(src)] = name
    return out


def parse_gat_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read width/height from GAT header (GRAT + ver + uint32 w/h)."""
    if len(data) < 14 or data[:4] != b"GRAT":
        return None
    width, height = struct.unpack_from("<II", data, 6)
    if width == 0 or height == 0:
        return None
    return int(width), int(height)


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
    display_names: dict[str, str] = {}
    dim_cache: dict[str, tuple[int, int] | None] = {}
    if grfs:
        raw = read_active_file(active, grfs, "data/resnametable.txt")
        if raw:
            aliases = parse_resnametable(raw)
        name_raw = read_active_file(active, grfs, "data/mapnametable.txt")
        if name_raw:
            display_names = parse_mapnametable(name_raw)

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

        display_name = display_names.get(mid)
        if display_name is None and "rsw" in via_alias:
            display_name = display_names.get(via_alias["rsw"])

        width = height = None
        if grfs and "gat" in resolved:
            gat_stem = resolved["gat"]
            if gat_stem not in dim_cache:
                gat_raw = read_active_file(active, grfs, f"data/{gat_stem}.gat")
                dim_cache[gat_stem] = (
                    parse_gat_dimensions(gat_raw) if gat_raw else None
                )
            dims = dim_cache[gat_stem]
            if dims:
                width, height = dims

        row = {
            "map_id": mid,
            "display_name": display_name,
            "width": width,
            "height": height,
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
            # Avoid matching unidentifiedX when asking for identifiedX
            # (unidentifiedResourceName ends with identifiedResourceName).
            mm = re.search(
                rf'(?<![A-Za-z]){name}\s*=\s*"((?:\\.|[^"\\])*)"', body
            )
            return mm.group(1) if mm else None

        def field_int(name: str) -> int | None:
            mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*(-?\d+)", body)
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
    # ResourceName lookup is case-insensitive (GRF stems vary in case).
    icon_by = {r["resource_name"].lower(): r for r in icons}
    spr_by = {r["sprite_stem"].lower(): r for r in sprites}
    out = []
    for row in info_rows:
        ident = row.get("identified_resource_name") or ""
        unid = row.get("unidentified_resource_name") or ""
        icon = icon_by.get(ident.lower()) if ident else None
        spr = spr_by.get(ident.lower()) if ident else None
        has_icon = bool(icon and icon.get("has_item"))
        has_coll = bool(icon and icon.get("has_collection"))
        has_spr = bool(spr and spr.get("has_spr") and spr.get("has_act"))
        enriched = dict(row)
        enriched["has_item_icon"] = has_icon
        enriched["has_collection"] = has_coll
        enriched["has_sprite"] = has_spr
        enriched["assets_complete"] = has_icon and has_coll and has_spr
        if unid and unid != ident:
            u_icon = icon_by.get(unid.lower())
            u_spr = spr_by.get(unid.lower())
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


def load_server_item_ids(rathena: Path) -> list[int]:
    ids: set[int] = set()
    for rel in SERVER_ITEM_DB_FILES:
        path = rathena / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^\s+-\s+Id:\s*(\d+)", text, re.M):
            ids.add(int(m.group(1)))
    return sorted(ids)


def build_server_item_gaps(
    server_ids: list[int],
    item_info: list[dict],
) -> list[dict]:
    by_id = {r["item_id"]: r for r in item_info}
    gaps: list[dict] = []
    for iid in server_ids:
        row = by_id.get(iid)
        if row is None:
            gaps.append(
                {
                    "item_id": iid,
                    "reason": "no_iteminfo",
                    "identified_resource_name": None,
                    "has_item_icon": False,
                    "has_collection": False,
                    "has_sprite": False,
                    "assets_complete": False,
                }
            )
            continue
        if not row.get("assets_complete"):
            gaps.append(
                {
                    "item_id": iid,
                    "reason": "missing_assets",
                    "identified_resource_name": row.get("identified_resource_name"),
                    "has_item_icon": bool(row.get("has_item_icon")),
                    "has_collection": bool(row.get("has_collection")),
                    "has_sprite": bool(row.get("has_sprite")),
                    "assets_complete": False,
                }
            )
    return gaps


def load_server_mobs(rathena: Path) -> list[dict]:
    """Return [{mob_id, aegis_name}, ...] from mob_db YAML."""
    by_id: dict[int, str] = {}
    for rel in SERVER_MOB_DB_FILES:
        path = rathena / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        cur: int | None = None
        for line in text.splitlines():
            m = re.match(r"^\s+-\s+Id:\s*(\d+)", line)
            if m:
                cur = int(m.group(1))
                by_id.setdefault(cur, "")
                continue
            m = re.match(r"^\s+AegisName:\s*(\S+)", line)
            if m and cur is not None:
                by_id[cur] = m.group(1)
    return [{"mob_id": mid, "aegis_name": an} for mid, an in sorted(by_id.items())]


def export_gr2_stems(active: dict[str, tuple[str, str]]) -> set[str]:
    """Lowercase stems of .gr2 files anywhere under data/."""
    out: set[str] = set()
    for key in active:
        if ext_of(key) != "gr2":
            continue
        out.add(stem_of(key).lower())
    return out


def index_wav_basenames(active: dict[str, tuple[str, str]]) -> set[str]:
    """Lowercase basenames of active data/wav/** entries."""
    out: set[str] = set()
    for key in active:
        if not key.startswith("data/wav/") or ext_of(key) != "wav":
            continue
        out.add(basename(key).lower())
    return out


def extract_act_wav_refs(act_blob: bytes) -> list[str]:
    """Unique .wav basenames embedded in an ACT (null-terminated sound events)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for m in _WAV_NULL_TERM_RE.finditer(act_blob):
        name = m.group(1).decode("ascii", errors="ignore").lower()
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def jobname_sprite_stems(jt_to_spr: dict[str, str]) -> set[str]:
    """Lowercase stems referenced by jobname (strip .gr2)."""
    out: set[str] = set()
    for spr in jt_to_spr.values():
        name = spr.strip()
        if not name:
            continue
        lower = name.lower()
        if lower.endswith(".gr2"):
            lower = lower[:-4]
        out.add(lower)
    return out


def _jobname_stem(spr: str) -> str:
    name = spr.strip()
    lower = name.lower()
    if lower.endswith(".gr2"):
        lower = lower[:-4]
    return lower


def attach_npc_sprite_ids(
    sprites: list[dict],
    id_to_jt: dict[int, str],
    jt_to_spr: dict[str, str],
) -> list[dict]:
    """Add numeric sprite_ids (+ jt_names) to each NPC sprite row.

    Scripts reference NPCs by numeric id (or JT constant). npcidentity maps
    id→JT_*; jobname maps JT_*→stem. Several ids may share one stem.
    """
    stem_to_ids: dict[str, list[int]] = {}
    stem_to_jt: dict[str, list[str]] = {}
    for sid, jt in id_to_jt.items():
        spr = jt_to_spr.get(jt)
        if not spr:
            continue
        stem = _jobname_stem(spr)
        stem_to_ids.setdefault(stem, []).append(sid)
        stem_to_jt.setdefault(stem, []).append(jt)
    out: list[dict] = []
    for row in sprites:
        enriched = dict(row)
        stem = row["sprite_stem"].lower()
        ids = sorted(stem_to_ids.get(stem, []))
        jts = sorted(set(stem_to_jt.get(stem, [])))
        enriched["sprite_ids"] = ids
        enriched["jt_names"] = jts
        out.append(enriched)
    return out


def filter_sprites_by_stems(
    sprites: list[dict], allowed: set[str]
) -> list[dict]:
    """Keep only sprite rows whose stem is in allowed (case-insensitive)."""
    return [r for r in sprites if r["sprite_stem"].lower() in allowed]


def enrich_sprite_act_deps(
    sprites: list[dict],
    active: dict[str, tuple[str, str]],
    grfs: dict[str, Grf],
    wav_names: set[str],
) -> tuple[list[dict], list[dict]]:
    """Attach ACT→wav coverage to sprite rows; return (rows, act_gaps).

    Gaps are one row per (sprite_stem, missing wav).
    """
    gaps: list[dict] = []
    out: list[dict] = []
    for row in sprites:
        enriched = dict(row)
        refs: list[str] = []
        missing: list[str] = []
        act_path = (row.get("paths") or {}).get("act")
        if row.get("has_act") and act_path:
            blob = read_active_file(active, grfs, act_path)
            if blob is not None:
                refs = extract_act_wav_refs(blob)
                missing = [w for w in refs if w not in wav_names]
        enriched["wav_refs"] = refs
        enriched["wav_missing"] = missing
        enriched["act_deps_complete"] = bool(row.get("has_act")) and not missing
        out.append(enriched)
        for wav in missing:
            gaps.append(
                {
                    "sprite_stem": row["sprite_stem"],
                    "act_path": act_path,
                    "wav": wav,
                    "reason": "missing_wav",
                }
            )
    return out, gaps


def parse_npcidentity(data: bytes) -> dict[int, str]:
    """id -> JT_* name from text npcidentity.lub."""
    text = data.decode("cp949", errors="replace")
    out: dict[int, str] = {}
    for m in re.finditer(r"(JT_\w+)\s*=\s*(\d+)", text):
        out[int(m.group(2))] = m.group(1)
    return out


def parse_jobname(data: bytes) -> dict[str, str]:
    """JT_* -> sprite name from text jobname.lub."""
    text = data.decode("cp949", errors="replace")
    out: dict[str, str] = {}
    for m in re.finditer(r"\[jobtbl\.(JT_\w+)\]\s*=\s*\"([^\"]+)\"", text):
        out[m.group(1)] = m.group(2)
    return out


def find_active_lub(
    active: dict[str, tuple[str, str]],
    grfs: dict[str, Grf],
    candidates: tuple[str, ...],
) -> bytes | None:
    for rel in candidates:
        raw = read_active_file(active, grfs, rel)
        if raw is not None:
            return raw
    return None


def mob_sprite_complete(
    sprite_name: str,
    mob_spr_by: dict[str, dict],
    gr2_stems: set[str],
) -> tuple[bool, str]:
    """Return (ok, kind) where kind is spr_act|gr2|missing."""
    name = sprite_name.strip()
    if not name:
        return False, "missing"
    lower = name.lower()
    if lower.endswith(".gr2"):
        stem = lower[:-4]
        if stem in gr2_stems:
            return True, "gr2"
        return False, "missing"
    slot = mob_spr_by.get(lower)
    if slot and slot.get("has_spr") and slot.get("has_act"):
        return True, "spr_act"
    return False, "missing"


def build_server_mob_gaps(
    server_mobs: list[dict],
    id_to_jt: dict[int, str],
    jt_to_spr: dict[str, str],
    mob_sprites: list[dict],
    gr2_stems: set[str],
) -> list[dict]:
    mob_spr_by = {r["sprite_stem"].lower(): r for r in mob_sprites}
    gaps: list[dict] = []
    for row in server_mobs:
        mid = row["mob_id"]
        aegis = row.get("aegis_name") or ""
        jt = id_to_jt.get(mid)
        if not jt:
            gaps.append(
                {
                    "mob_id": mid,
                    "aegis_name": aegis or None,
                    "reason": "no_identity",
                    "jt": None,
                    "sprite_name": None,
                    "sprite_kind": None,
                    "has_sprite": False,
                }
            )
            continue
        spr = jt_to_spr.get(jt)
        if not spr:
            gaps.append(
                {
                    "mob_id": mid,
                    "aegis_name": aegis or None,
                    "reason": "no_jobname",
                    "jt": jt,
                    "sprite_name": None,
                    "sprite_kind": None,
                    "has_sprite": False,
                }
            )
            continue
        ok, kind = mob_sprite_complete(spr, mob_spr_by, gr2_stems)
        if not ok:
            gaps.append(
                {
                    "mob_id": mid,
                    "aegis_name": aegis or None,
                    "reason": "missing_sprite",
                    "jt": jt,
                    "sprite_name": spr,
                    "sprite_kind": kind,
                    "has_sprite": False,
                }
            )
    return gaps


def parse_skillid(data: bytes) -> dict[str, int]:
    """SKID name → numeric id from skillid.lub."""
    text = data.decode("utf-8", errors="replace")
    out: dict[str, int] = {}
    for m in re.finditer(r"(\w+)\s*=\s*(\d+)", text):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_skillinfolist(data: bytes) -> dict[str, dict]:
    """SKID name → {resource_name, display_name, max_lv, type}."""
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
    out: dict[str, dict] = {}
    # last table entry omits the trailing comma before closing `}`
    block_re = re.compile(r"\[SKID\.(\w+)\]\s*=\s*\{(.*?)\n\t\},?", re.S)
    for m in block_re.finditer(text):
        sk = m.group(1)
        body = m.group(2)
        res_m = re.search(r'^\s*"((?:\\.|[^"\\])*)"', body, re.M)
        name_m = re.search(r'SkillName\s*=\s*"((?:\\.|[^"\\])*)"', body)
        max_m = re.search(r"MaxLv\s*=\s*(\d+)", body)
        type_m = re.search(r'Type\s*=\s*"((?:\\.|[^"\\])*)"', body)
        out[sk] = {
            "resource_name": res_m.group(1) if res_m else sk,
            "display_name": name_m.group(1) if name_m else None,
            "max_lv": int(max_m.group(1)) if max_m else None,
            "type": type_m.group(1) if type_m else None,
        }
    return out


def parse_skilldescript_titles(data: bytes) -> dict[str, str]:
    """SKID name → first description line (display title)."""
    text = data.decode("utf-8", errors="replace")
    out: dict[str, str] = {}
    for m in re.finditer(
        r'\[SKID\.(\w+)\]\s*=\s*\{\s*"((?:\\.|[^"\\])*)"', text
    ):
        out[m.group(1)] = m.group(2)
    return out


def _skill_icon_key(resource_name: str) -> str:
    return (
        "data/texture/유저인터페이스/item/"
        + resource_name.lower()
        + ".bmp"
    )


def export_skills(
    active: dict[str, tuple[str, str]],
    skill_ids: dict[str, int],
    info_by: dict[str, dict],
    descript_titles: dict[str, str],
    item_sprites: list[dict],
) -> list[dict]:
    """Catalog client skills: id, names, icon/sprite presence."""
    spr_by = {r["sprite_stem"].lower(): r for r in item_sprites}
    names = sorted(set(skill_ids) | set(info_by) | set(descript_titles))
    rows: list[dict] = []
    for sk in names:
        info = info_by.get(sk) or {}
        resource = info.get("resource_name") or sk
        display = info.get("display_name")
        descript_title = descript_titles.get(sk)
        icon_key = _skill_icon_key(resource)
        icon_hit = active.get(icon_key)
        # also accept non-bmp under same stem via _ui path variants
        if icon_hit is None:
            for ext in ("tga", "png"):
                alt = icon_key[:-3] + ext
                icon_hit = active.get(alt)
                if icon_hit:
                    icon_key = alt
                    break
        spr = spr_by.get(resource.lower())
        has_icon = icon_hit is not None
        has_spr = bool(spr and spr.get("has_spr") and spr.get("has_act"))

        # if SkillName missing, promote descript title to display
        if not display and descript_title:
            display = descript_title
        alt_names: list[str] = []
        seen = {sk, resource, display}
        for cand in (info.get("display_name"), descript_title):
            if not cand or cand in seen:
                continue
            seen.add(cand)
            alt_names.append(cand)

        row: dict = {
            "skill_id": skill_ids.get(sk),
            "aegis_name": sk,
            "resource_name": resource,
            "display_name": display,
            "descript_title": descript_title,
            "alt_names": alt_names,
            "max_lv": info.get("max_lv"),
            "type": info.get("type"),
            "has_skillinfo": sk in info_by,
            "has_descript": sk in descript_titles,
            "has_icon": has_icon,
            "has_sprite": has_spr,
            "assets_complete": has_icon,
        }
        if has_icon and icon_hit:
            row["icon_path"] = icon_hit[1].replace("\\", "/")
            row["icon_winner_grf"] = icon_hit[0]
        rows.append(row)
    rows.sort(
        key=lambda r: (
            r["skill_id"] is None,
            r["skill_id"] if r["skill_id"] is not None else 0,
            r["aegis_name"],
        )
    )
    return rows


def load_server_skills(rathena: Path) -> list[dict]:
    """Return [{skill_id, aegis_name, description}, ...] from skill_db YAML."""
    by_id: dict[int, dict] = {}
    for rel in SERVER_SKILL_DB_FILES:
        path = rathena / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        cur_id: int | None = None
        cur_name: str | None = None
        cur_desc: str | None = None

        def flush() -> None:
            nonlocal cur_id, cur_name, cur_desc
            if cur_id is None:
                return
            by_id[cur_id] = {
                "skill_id": cur_id,
                "aegis_name": cur_name,
                "description": cur_desc,
            }
            cur_id, cur_name, cur_desc = None, None, None

        for line in text.splitlines():
            m = re.match(r"^\s+-\s+Id:\s*(\d+)", line)
            if m:
                flush()
                cur_id = int(m.group(1))
                continue
            if cur_id is None:
                continue
            m = re.match(r"^\s+Name:\s*(.+)$", line)
            if m:
                cur_name = m.group(1).strip().strip("\"'")
                continue
            m = re.match(r"^\s+Description:\s*(.+)$", line)
            if m:
                cur_desc = m.group(1).strip().strip("\"'")
        flush()
    return [by_id[i] for i in sorted(by_id)]


def build_server_skill_gaps(
    server_skills: list[dict],
    client_skills: list[dict],
) -> list[dict]:
    by_id = {r["skill_id"]: r for r in client_skills if r.get("skill_id") is not None}
    by_name = {r["aegis_name"]: r for r in client_skills}
    gaps: list[dict] = []
    for s in server_skills:
        sid = s["skill_id"]
        aegis = s.get("aegis_name") or ""
        row = by_id.get(sid) or (by_name.get(aegis) if aegis else None)
        if row is None:
            gaps.append(
                {
                    "skill_id": sid,
                    "aegis_name": aegis or None,
                    "reason": "no_client",
                    "display_name": s.get("description"),
                    "has_skillinfo": False,
                    "has_icon": False,
                }
            )
            continue
        if not row.get("has_skillinfo"):
            gaps.append(
                {
                    "skill_id": sid,
                    "aegis_name": row.get("aegis_name") or aegis or None,
                    "reason": "no_skillinfo",
                    "display_name": row.get("display_name") or s.get("description"),
                    "has_skillinfo": False,
                    "has_icon": bool(row.get("has_icon")),
                }
            )
            continue
        if not row.get("has_icon"):
            gaps.append(
                {
                    "skill_id": sid,
                    "aegis_name": row.get("aegis_name") or aegis or None,
                    "reason": "missing_icon",
                    "display_name": row.get("display_name") or s.get("description"),
                    "has_skillinfo": True,
                    "has_icon": False,
                }
            )
    return gaps


def enrich_skills_with_server(
    client_skills: list[dict],
    server_skills: list[dict],
) -> list[dict]:
    """Attach server Description as alt name when it differs from client display."""
    by_id = {s["skill_id"]: s for s in server_skills}
    by_name = {
        s["aegis_name"]: s for s in server_skills if s.get("aegis_name")
    }
    out: list[dict] = []
    for row in client_skills:
        enriched = dict(row)
        srv = None
        if row.get("skill_id") is not None:
            srv = by_id.get(row["skill_id"])
        if srv is None:
            srv = by_name.get(row["aegis_name"])
        if srv:
            enriched["server_aegis_name"] = srv.get("aegis_name")
            enriched["server_description"] = srv.get("description")
            desc = srv.get("description")
            if desc:
                seen = {
                    row.get("aegis_name"),
                    row.get("resource_name"),
                    row.get("display_name"),
                    row.get("descript_title"),
                    *(row.get("alt_names") or []),
                }
                if desc not in seen:
                    enriched["alt_names"] = [*(row.get("alt_names") or []), desc]
            enriched["in_server_db"] = True
        else:
            enriched["in_server_db"] = False
        out.append(enriched)
    return out


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
    ap.add_argument(
        "--rathena",
        type=Path,
        default=None,
        help="default: <cli-root>/../rathena — enables item/mob/skill server gap reports",
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
    rathena: Path = (
        args.rathena.resolve()
        if args.rathena
        else (cli_root.parent / "rathena").resolve()
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
        npc_spr_all = export_sprite_dir(active, {"npc", "엔피씨"})
        gr2_stems = export_gr2_stems(active)
        wav_names = index_wav_basenames(active)

        print("parsing npcidentity / jobname…", flush=True)
        id_to_jt: dict[int, str] = {}
        jt_to_spr: dict[str, str] = {}
        ident_raw = find_active_lub(active, grfs, NPCIDENTITY_CANDIDATES)
        job_raw = find_active_lub(active, grfs, JOBNAME_CANDIDATES)
        if ident_raw:
            id_to_jt = parse_npcidentity(ident_raw)
        if job_raw:
            jt_to_spr = parse_jobname(job_raw)
        wired_stems = jobname_sprite_stems(jt_to_spr)
        # Inventory NPCs = usable only (referenced by jobname), not loose GRF files.
        npc_spr = filter_sprites_by_stems(npc_spr_all, wired_stems)
        npc_spr = attach_npc_sprite_ids(npc_spr, id_to_jt, jt_to_spr)
        npc_with_ids = sum(1 for r in npc_spr if r.get("sprite_ids"))
        print(
            f"  identity ids={len(id_to_jt)} jobname entries={len(jt_to_spr)} "
            f"gr2_stems={len(gr2_stems)} "
            f"npc_files={len(npc_spr_all)} npc_wired={len(npc_spr)} "
            f"npc_with_sprite_ids={npc_with_ids}",
            flush=True,
        )

        print(
            f"scanning mob/npc ACT→wav deps (wavs indexed={len(wav_names)})…",
            flush=True,
        )
        mob_spr, mob_act_gaps = enrich_sprite_act_deps(
            mob_spr, active, grfs, wav_names
        )
        print(
            f"  mob act gaps={len(mob_act_gaps)} "
            f"stems_incomplete="
            f"{sum(1 for r in mob_spr if r.get('has_act') and not r.get('act_deps_complete'))}",
            flush=True,
        )
        npc_spr, npc_act_gaps = enrich_sprite_act_deps(
            npc_spr, active, grfs, wav_names
        )
        print(
            f"  npc act gaps={len(npc_act_gaps)} "
            f"stems_incomplete="
            f"{sum(1 for r in npc_spr if r.get('has_act') and not r.get('act_deps_complete'))}",
            flush=True,
        )

        item_info_path = find_item_info(cli_root)
        item_info: list[dict] = []
        if item_info_path:
            print(f"parsing itemInfo: {item_info_path}", flush=True)
            item_info = enrich_item_info(
                parse_item_info(item_info_path), icons, item_spr
            )

        print("parsing skillid / skillinfolist / skilldescript…", flush=True)
        skill_ids: dict[str, int] = {}
        skill_info_by: dict[str, dict] = {}
        skill_descript_titles: dict[str, str] = {}
        skillid_raw = find_active_lub(active, grfs, SKILLID_CANDIDATES)
        skillinfo_raw = find_active_lub(active, grfs, SKILLINFOLIST_CANDIDATES)
        skilldesc_raw = find_active_lub(active, grfs, SKILLDESCRIPT_CANDIDATES)
        if skillid_raw:
            skill_ids = parse_skillid(skillid_raw)
        if skillinfo_raw:
            skill_info_by = parse_skillinfolist(skillinfo_raw)
        if skilldesc_raw:
            skill_descript_titles = parse_skilldescript_titles(skilldesc_raw)
        skills = export_skills(
            active, skill_ids, skill_info_by, skill_descript_titles, item_spr
        )
        print(
            f"  skillid={len(skill_ids)} skillinfo={len(skill_info_by)} "
            f"descript={len(skill_descript_titles)} catalog={len(skills)} "
            f"with_icon={sum(1 for r in skills if r.get('has_icon'))}",
            flush=True,
        )

        server_gaps: list[dict] = []
        server_ids: list[int] = []
        server_mobs: list[dict] = []
        mob_gaps: list[dict] = []
        server_skills: list[dict] = []
        skill_gaps: list[dict] = []
        if rathena.is_dir():
            print(f"loading server dbs: {rathena}", flush=True)
            server_ids = load_server_item_ids(rathena)
            server_gaps = build_server_item_gaps(server_ids, item_info)
            server_mobs = load_server_mobs(rathena)
            mob_gaps = build_server_mob_gaps(
                server_mobs, id_to_jt, jt_to_spr, mob_spr, gr2_stems
            )
            server_skills = load_server_skills(rathena)
            skills = enrich_skills_with_server(skills, server_skills)
            skill_gaps = build_server_skill_gaps(server_skills, skills)
        else:
            print(f"skip server gaps (rathena missing): {rathena}", flush=True)

        out_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(out_dir / "client_maps.jsonl", maps)
        write_jsonl(out_dir / "client_item_icons.jsonl", icons)
        write_jsonl(out_dir / "client_item_sprites.jsonl", item_spr)
        write_jsonl(out_dir / "client_mob_sprites.jsonl", mob_spr)
        write_jsonl(out_dir / "client_mob_act_gaps.jsonl", mob_act_gaps)
        write_jsonl(out_dir / "client_npc_sprites.jsonl", npc_spr)
        write_jsonl(out_dir / "client_npc_act_gaps.jsonl", npc_act_gaps)
        write_jsonl(out_dir / "client_skills.jsonl", skills)
        if item_info:
            write_jsonl(out_dir / "client_item_info.jsonl", item_info)
        if server_gaps or server_ids:
            write_jsonl(out_dir / "client_item_server_gaps.jsonl", server_gaps)
        if mob_gaps or server_mobs:
            write_jsonl(out_dir / "client_mob_server_gaps.jsonl", mob_gaps)
        if skill_gaps or server_skills:
            write_jsonl(out_dir / "client_skill_server_gaps.jsonl", skill_gaps)

        maps_alias = sum(1 for r in maps if r.get("alias_of"))
        maps_alias_complete = sum(
            1 for r in maps if r.get("alias_of") and r["complete"]
        )
        items_server = len(server_ids)
        items_no_iteminfo = sum(1 for g in server_gaps if g["reason"] == "no_iteminfo")
        items_missing_assets = sum(
            1 for g in server_gaps if g["reason"] == "missing_assets"
        )
        items_server_ok = items_server - items_no_iteminfo - items_missing_assets
        mobs_server = len(server_mobs)
        mobs_no_identity = sum(1 for g in mob_gaps if g["reason"] == "no_identity")
        mobs_no_jobname = sum(1 for g in mob_gaps if g["reason"] == "no_jobname")
        mobs_missing_sprite = sum(
            1 for g in mob_gaps if g["reason"] == "missing_sprite"
        )
        mobs_server_ok = (
            mobs_server - mobs_no_identity - mobs_no_jobname - mobs_missing_sprite
        )
        mobs_act_incomplete = sum(
            1
            for r in mob_spr
            if r.get("has_act") and not r.get("act_deps_complete")
        )
        mob_wav_missing_unique = sorted({g["wav"] for g in mob_act_gaps})
        skills_with_icon = sum(1 for r in skills if r.get("has_icon"))
        skills_with_info = sum(1 for r in skills if r.get("has_skillinfo"))
        skills_with_display = sum(1 for r in skills if r.get("display_name"))
        skills_with_alt = sum(1 for r in skills if r.get("alt_names"))
        skills_server = len(server_skills)
        skills_no_client = sum(1 for g in skill_gaps if g["reason"] == "no_client")
        skills_no_skillinfo = sum(
            1 for g in skill_gaps if g["reason"] == "no_skillinfo"
        )
        skills_missing_icon = sum(
            1 for g in skill_gaps if g["reason"] == "missing_icon"
        )
        skills_server_ok = (
            skills_server
            - skills_no_client
            - skills_no_skillinfo
            - skills_missing_icon
        )
        meta = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_ini": str(ini_path.relative_to(cli_root)),
            "data_ini_order": ini_order,
            "grf_paths": {m["label"]: m["path"] for m in grf_meta},
            "grfs": grf_meta,
            "active_path_count": len(active),
            "rathena": str(rathena)
            if (server_ids or server_mobs or server_skills)
            else None,
            "counts": {
                "maps": len(maps),
                "maps_complete": sum(1 for r in maps if r["complete"]),
                "maps_with_display_name": sum(
                    1 for r in maps if r.get("display_name")
                ),
                "maps_with_dimensions": sum(
                    1 for r in maps if r.get("width") and r.get("height")
                ),
                "maps_alias": maps_alias,
                "maps_alias_complete": maps_alias_complete,
                "item_icons": len(icons),
                "item_sprites": len(item_spr),
                "item_info": len(item_info),
                "item_info_assets_complete": sum(
                    1 for r in item_info if r.get("assets_complete")
                ),
                "items_server": items_server,
                "items_server_ok": items_server_ok,
                "items_no_iteminfo": items_no_iteminfo,
                "items_missing_assets": items_missing_assets,
                "mob_sprites": len(mob_spr),
                "mob_gr2_stems": len(gr2_stems),
                "mob_wavs_indexed": len(wav_names),
                "mobs_act_deps_incomplete": mobs_act_incomplete,
                "mobs_act_gap_rows": len(mob_act_gaps),
                "mobs_act_wav_missing_unique": len(mob_wav_missing_unique),
                "mobs_server": mobs_server,
                "mobs_server_ok": mobs_server_ok,
                "mobs_no_identity": mobs_no_identity,
                "mobs_no_jobname": mobs_no_jobname,
                "mobs_missing_sprite": mobs_missing_sprite,
                "npc_sprites": len(npc_spr),
                "npc_sprites_files": len(npc_spr_all),
                "npc_sprites_unwired": len(npc_spr_all) - len(npc_spr),
                "npc_sprites_with_ids": sum(
                    1 for r in npc_spr if r.get("sprite_ids")
                ),
                "npcs_act_deps_incomplete": sum(
                    1
                    for r in npc_spr
                    if r.get("has_act") and not r.get("act_deps_complete")
                ),
                "npcs_act_gap_rows": len(npc_act_gaps),
                "npcs_act_wav_missing_unique": len(
                    {g["wav"] for g in npc_act_gaps}
                ),
                "skills": len(skills),
                "skills_with_skillinfo": skills_with_info,
                "skills_with_display_name": skills_with_display,
                "skills_with_alt_names": skills_with_alt,
                "skills_with_icon": skills_with_icon,
                "skills_with_sprite": sum(1 for r in skills if r.get("has_sprite")),
                "skills_missing_icon": len(skills) - skills_with_icon,
                "skills_server": skills_server,
                "skills_server_ok": skills_server_ok,
                "skills_no_client": skills_no_client,
                "skills_no_skillinfo": skills_no_skillinfo,
                "skills_server_missing_icon": skills_missing_icon,
            },
            "outputs": [
                "client_grf_index_meta.json",
                "client_maps.jsonl",
                "client_item_icons.jsonl",
                "client_item_sprites.jsonl",
                "client_item_info.jsonl" if item_info else None,
                "client_item_server_gaps.jsonl" if server_ids else None,
                "client_mob_sprites.jsonl",
                "client_mob_act_gaps.jsonl",
                "client_mob_server_gaps.jsonl" if server_mobs else None,
                "client_npc_sprites.jsonl",
                "client_npc_act_gaps.jsonl",
                "client_skills.jsonl",
                "client_skill_server_gaps.jsonl" if server_skills else None,
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
