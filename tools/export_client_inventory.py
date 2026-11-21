#!/usr/bin/env python3
"""Export machine-readable client asset inventory (JSONL + meta).

Reads data.ini priority (first wins). Writes reports under --out-dir:

  client_grf_index_meta.json
  client_maps.jsonl
  client_item_icons.jsonl
  client_item_sprites.jsonl
  client_item_info.jsonl      # from System/itemInfo_EN.lua when present
  client_item_server_gaps.jsonl  # server items missing itemInfo or assets
  client_mob_sprites.jsonl
  client_mob_server_gaps.jsonl   # server mobs missing identity/jobname/sprite
  client_mob_act_gaps.jsonl      # mob ACT→wav refs missing from client stack
  client_npc_sprites.jsonl
  client_npc_act_gaps.jsonl      # npc ACT→wav refs missing from client stack

Example:
  python3 tools/export_client_inventory.py \\
      --cli-root . --out-dir ../ozro-data/reports --rathena ../rathena
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

SCHEMA_VERSION = 5

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
        help="default: <cli-root>/../rathena — enables item/mob server gap reports",
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
        npc_spr = export_sprite_dir(active, {"npc", "엔피씨"})
        gr2_stems = export_gr2_stems(active)
        wav_names = index_wav_basenames(active)
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

        print("parsing npcidentity / jobname…", flush=True)
        id_to_jt: dict[int, str] = {}
        jt_to_spr: dict[str, str] = {}
        ident_raw = find_active_lub(active, grfs, NPCIDENTITY_CANDIDATES)
        job_raw = find_active_lub(active, grfs, JOBNAME_CANDIDATES)
        if ident_raw:
            id_to_jt = parse_npcidentity(ident_raw)
        if job_raw:
            jt_to_spr = parse_jobname(job_raw)
        print(
            f"  identity ids={len(id_to_jt)} jobname entries={len(jt_to_spr)} "
            f"gr2_stems={len(gr2_stems)}",
            flush=True,
        )

        server_gaps: list[dict] = []
        server_ids: list[int] = []
        server_mobs: list[dict] = []
        mob_gaps: list[dict] = []
        if rathena.is_dir():
            print(f"loading server dbs: {rathena}", flush=True)
            server_ids = load_server_item_ids(rathena)
            server_gaps = build_server_item_gaps(server_ids, item_info)
            server_mobs = load_server_mobs(rathena)
            mob_gaps = build_server_mob_gaps(
                server_mobs, id_to_jt, jt_to_spr, mob_spr, gr2_stems
            )
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
        if item_info:
            write_jsonl(out_dir / "client_item_info.jsonl", item_info)
        if server_gaps or server_ids:
            write_jsonl(out_dir / "client_item_server_gaps.jsonl", server_gaps)
        if mob_gaps or server_mobs:
            write_jsonl(out_dir / "client_mob_server_gaps.jsonl", mob_gaps)

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
        meta = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_ini": str(ini_path.relative_to(cli_root)),
            "data_ini_order": ini_order,
            "grf_paths": {m["label"]: m["path"] for m in grf_meta},
            "grfs": grf_meta,
            "active_path_count": len(active),
            "rathena": str(rathena) if (server_ids or server_mobs) else None,
            "counts": {
                "maps": len(maps),
                "maps_complete": sum(1 for r in maps if r["complete"]),
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
                "npcs_act_deps_incomplete": sum(
                    1
                    for r in npc_spr
                    if r.get("has_act") and not r.get("act_deps_complete")
                ),
                "npcs_act_gap_rows": len(npc_act_gaps),
                "npcs_act_wav_missing_unique": len(
                    {g["wav"] for g in npc_act_gaps}
                ),
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
