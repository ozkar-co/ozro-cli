#!/usr/bin/env python3
"""Build queryable client description JSONL for the site.

Sources (client-only lore / display data, intentionally out of ozro_* SQL):
  - System/itemInfo_EN.lua  → client_item_descriptions.jsonl
  - skillinfoz/{skillid,skillinfolist,skilldescript}.lub → client_skill_descriptions.jsonl

Example:
  python3 tools/build_client_descriptions.py \\
      --cli-root . --out-dir ../ozro-data/reports
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_client_inventory import (  # noqa: E402
    SKILLDESCRIPT_CANDIDATES,
    SKILLID_CANDIDATES,
    SKILLINFOLIST_CANDIDATES,
    Grf,
    GrfError,
    build_index,
    find_item_info,
    parse_data_ini,
    parse_skillid,
    read_active_file,
    write_jsonl,
)

SCHEMA_VERSION = 1

_ITEM_BLOCK_RE = re.compile(rb"\[(\d+)\]\s*=\s*\{(.*?)\n\t\},?", re.S)
_SKILL_BLOCK_RE = re.compile(r"\[SKID\.(\w+)\]\s*=\s*\{(.*?)\n\t\},?", re.S)
_LUA_STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
_INT_LIST_RE = re.compile(r"=\s*\{([^}]*)\}")
_NEED_SKILL_RE = re.compile(r"\{\s*SKID\.(\w+)\s*,\s*(\d+)\s*\}")
_SKILL_SCALE_RE = re.compile(
    r"\[(\d+)\]\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*,\s*y\s*=\s*(-?\d+)\s*\}"
)


def _unescape_lua(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _decode_text(raw: bytes) -> str:
    """Visible EN client text is ISO-8859-1 / latin-1."""
    return raw.decode("latin-1")


def _decode_resource(raw: bytes) -> str:
    for enc in ("cp949", "euc-kr", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _field_str_bytes(body: bytes, name: str) -> str | None:
    mm = re.search(
        rf'(?<![A-Za-z]){name}\s*=\s*"((?:\\.|[^"\\])*)"'.encode(), body
    )
    if not mm:
        return None
    return _unescape_lua(_decode_text(mm.group(1)))


def _field_resource(body: bytes, name: str) -> str | None:
    mm = re.search(
        rf'(?<![A-Za-z]){name}\s*=\s*"((?:\\.|[^"\\])*)"'.encode(), body
    )
    if not mm:
        return None
    return _unescape_lua(_decode_resource(mm.group(1)))


def _field_int(body: bytes, name: str) -> int | None:
    mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*(-?\d+)".encode(), body)
    return int(mm.group(1)) if mm else None


def _field_bool(body: bytes, name: str) -> bool | None:
    mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*(true|false)".encode(), body)
    if not mm:
        return None
    return mm.group(1) == b"true"


def _extract_string_array(body: bytes, name: str) -> list[str] | None:
    """Pull ordered \"...\" strings from `name = { ... }` (handles nested braces)."""
    key = re.search(
        rf"(?:^|[\r\n])[ \t]*{name}[ \t]*=[ \t]*\{{".encode(), body
    )
    if not key:
        return None
    open_at = key.end() - 1
    depth = 0
    in_string = False
    escape = False
    i = open_at
    while i < len(body):
        ch = body[i]
        if in_string:
            if escape:
                escape = False
            elif ch == ord("\\"):
                escape = True
            elif ch == ord('"'):
                in_string = False
            i += 1
            continue
        if ch == ord('"'):
            in_string = True
        elif ch == ord("{"):
            depth += 1
        elif ch == ord("}"):
            depth -= 1
            if depth == 0:
                break
        i += 1
    else:
        return None

    inner = _decode_text(body[open_at + 1 : i])
    return [_unescape_lua(m.group(1)) for m in _LUA_STRING_RE.finditer(inner)]


def parse_item_descriptions(path: Path) -> list[dict]:
    raw = path.read_bytes()
    rows: list[dict] = []
    for m in _ITEM_BLOCK_RE.finditer(raw):
        item_id = int(m.group(1))
        body = m.group(2)
        row: dict = {
            "item_id": item_id,
            "identified_display_name": _field_str_bytes(
                body, "identifiedDisplayName"
            ),
            "unidentified_display_name": _field_str_bytes(
                body, "unidentifiedDisplayName"
            ),
            "identified_description": _extract_string_array(
                body, "identifiedDescriptionName"
            )
            or [],
            "unidentified_description": _extract_string_array(
                body, "unidentifiedDescriptionName"
            )
            or [],
            "identified_resource_name": _field_resource(
                body, "identifiedResourceName"
            ),
            "unidentified_resource_name": _field_resource(
                body, "unidentifiedResourceName"
            ),
            "slot_count": _field_int(body, "slotCount"),
            "class_num": _field_int(body, "ClassNum"),
            "costume": _field_bool(body, "costume"),
        }
        effect_id = _field_int(body, "EffectID")
        if effect_id is not None:
            row["effect_id"] = effect_id
        server = _field_str_bytes(body, "Server")
        if server:
            row["server"] = server
        rows.append(row)
    rows.sort(key=lambda r: r["item_id"])
    return rows


def _field_str(body: str, name: str) -> str | None:
    mm = re.search(rf'(?<![A-Za-z]){name}\s*=\s*"((?:\\.|[^"\\])*)"', body)
    return _unescape_lua(mm.group(1)) if mm else None


def _field_int_str(body: str, name: str) -> int | None:
    mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*(-?\d+)", body)
    return int(mm.group(1)) if mm else None


def _field_bool_str(body: str, name: str) -> bool | None:
    mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*(true|false)", body)
    if not mm:
        return None
    return mm.group(1) == "true"


def _int_list(body: str, name: str) -> list[int] | None:
    mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*\{{([^}}]*)\}}", body)
    if not mm:
        return None
    return [int(x) for x in re.findall(r"-?\d+", mm.group(1))]


def _need_skills(body: str) -> list[dict] | None:
    # Prefer Job-specific _NeedSkillList when present; else NeedSkillList.
    chunk = None
    for name in ("_NeedSkillList", "NeedSkillList"):
        mm = re.search(rf"(?<![A-Za-z]){name}\s*=\s*\{{", body)
        if not mm:
            continue
        # take until matching depth is hard; regex pairs is enough for this file
        start = mm.end() - 1
        depth = 0
        for i in range(start, len(body)):
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
                if depth == 0:
                    chunk = body[start + 1 : i]
                    break
        if chunk is not None:
            break
    if chunk is None:
        return None
    pairs = [
        {"skill": sk, "level": int(lv)} for sk, lv in _NEED_SKILL_RE.findall(chunk)
    ]
    return pairs or None


def _skill_scale(body: str) -> list[dict] | None:
    mm = re.search(r"(?<![A-Za-z])SkillScale\s*=\s*\{", body)
    if not mm:
        return None
    start = mm.end() - 1
    depth = 0
    end = None
    for i in range(start, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return None
    chunk = body[start + 1 : end]
    rows = [
        {"level": int(lv), "x": int(x), "y": int(y)}
        for lv, x, y in _SKILL_SCALE_RE.findall(chunk)
    ]
    return rows or None


def parse_skill_descriptions(
    skill_ids: dict[str, int],
    info_raw: bytes | None,
    descript_raw: bytes | None,
) -> list[dict]:
    info_by: dict[str, dict] = {}
    if info_raw:
        text = info_raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
        for m in _SKILL_BLOCK_RE.finditer(text):
            sk = m.group(1)
            body = m.group(2)
            res_m = re.search(r'^\s*"((?:\\.|[^"\\])*)"', body, re.M)
            info_by[sk] = {
                "resource_name": _unescape_lua(res_m.group(1)) if res_m else sk,
                "display_name": _field_str(body, "SkillName"),
                "max_lv": _field_int_str(body, "MaxLv"),
                "type": _field_str(body, "Type"),
                "sp_amount": _int_list(body, "SpAmount"),
                "ap_amount": _int_list(body, "ApAmount"),
                "attack_range": _int_list(body, "AttackRange"),
                "separate_lv": _field_bool_str(body, "bSeperateLv"),
                "need_skills": _need_skills(body),
                "skill_scale": _skill_scale(body),
            }

    descript_by: dict[str, list[str]] = {}
    if descript_raw:
        text = descript_raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
        for m in _SKILL_BLOCK_RE.finditer(text):
            sk = m.group(1)
            body = m.group(2)
            lines = [_unescape_lua(s) for s in _LUA_STRING_RE.findall(body)]
            descript_by[sk] = lines

    names = sorted(set(skill_ids) | set(info_by) | set(descript_by))
    rows: list[dict] = []
    for sk in names:
        info = info_by.get(sk) or {}
        lines = descript_by.get(sk) or []
        display = info.get("display_name")
        if not display and lines:
            display = lines[0]
        row: dict = {
            "skill_id": skill_ids.get(sk),
            "aegis_name": sk,
            "display_name": display,
            "description": lines,
            "resource_name": info.get("resource_name") or sk,
            "max_lv": info.get("max_lv"),
            "type": info.get("type"),
            "sp_amount": info.get("sp_amount"),
            "attack_range": info.get("attack_range"),
            "separate_lv": info.get("separate_lv"),
        }
        if info.get("ap_amount") is not None:
            row["ap_amount"] = info["ap_amount"]
        if info.get("need_skills") is not None:
            row["need_skills"] = info["need_skills"]
        if info.get("skill_scale") is not None:
            row["skill_scale"] = info["skill_scale"]
        rows.append(row)

    rows.sort(
        key=lambda r: (
            r["skill_id"] is None,
            r["skill_id"] if r["skill_id"] is not None else 0,
            r["aegis_name"],
        )
    )
    return rows


def _read_skill_blob(
    active: dict[str, tuple[str, str]],
    grfs: dict[str, Grf],
    candidates: tuple[str, ...],
) -> tuple[str | None, bytes | None]:
    for rel in candidates:
        raw = read_active_file(active, grfs, rel)
        if raw:
            return rel, raw
    return None, None


def build(cli_root: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    item_path = find_item_info(cli_root)
    if item_path is None:
        # also accept ozro-site copy
        site = cli_root.parent / "ozro-site" / "data" / "itemInfo_EN.lua"
        if site.is_file():
            item_path = site
    if item_path is None:
        raise FileNotFoundError(
            "itemInfo_EN.lua not found (patch/System or ozro-site/data)"
        )

    print(f"parsing itemInfo: {item_path}", flush=True)
    items = parse_item_descriptions(item_path)

    ini_path = cli_root / "patch" / "data.ini"
    if not ini_path.is_file():
        raise FileNotFoundError(f"missing {ini_path}")
    ini_order = parse_data_ini(ini_path)
    print(f"indexing GRF stack ({len(ini_order)} entries)…", flush=True)
    active, grf_meta = build_index(cli_root, ini_order)
    grfs = {m["label"]: Grf(cli_root / m["path"]) for m in grf_meta}

    print("reading skillid / skillinfolist / skilldescript…", flush=True)
    skillid_path, skillid_raw = _read_skill_blob(
        active, grfs, SKILLID_CANDIDATES
    )
    info_path, info_raw = _read_skill_blob(
        active, grfs, SKILLINFOLIST_CANDIDATES
    )
    desc_path, desc_raw = _read_skill_blob(
        active, grfs, SKILLDESCRIPT_CANDIDATES
    )
    if not skillid_raw:
        raise FileNotFoundError("skillid.lub not found in GRF stack")

    skill_ids = parse_skillid(skillid_raw)
    skills = parse_skill_descriptions(skill_ids, info_raw, desc_raw)

    items_out = out_dir / "client_item_descriptions.jsonl"
    skills_out = out_dir / "client_skill_descriptions.jsonl"
    write_jsonl(items_out, items)
    write_jsonl(skills_out, skills)

    meta = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "item_info": str(item_path),
            "skillid": skillid_path,
            "skillinfolist": info_path,
            "skilldescript": desc_path,
            "grf_stack": [
                {"priority": m["priority"], "label": m["label"], "file": m["file"]}
                for m in grf_meta
            ],
        },
        "counts": {
            "items": len(items),
            "items_with_identified_description": sum(
                1 for r in items if any(line.strip() for line in r["identified_description"])
            ),
            "items_with_effect_id": sum(1 for r in items if "effect_id" in r),
            "items_costume": sum(1 for r in items if r.get("costume")),
            "skills": len(skills),
            "skills_with_description": sum(
                1 for r in skills if r.get("description")
            ),
            "skills_with_id": sum(1 for r in skills if r.get("skill_id") is not None),
        },
        "outputs": [
            items_out.name,
            skills_out.name,
            "client_descriptions_meta.json",
        ],
    }
    (out_dir / "client_descriptions_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cli-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="ozro-cli root (default: repo root)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output directory (default: ../ozro-data/reports)",
    )
    args = ap.parse_args(argv)
    cli_root = args.cli_root.resolve()
    out_dir = (
        args.out_dir.resolve()
        if args.out_dir
        else (cli_root.parent / "ozro-data" / "reports").resolve()
    )
    try:
        meta = build(cli_root, out_dir)
    except (GrfError, OSError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    c = meta["counts"]
    print(
        f"wrote {c['items']} items, {c['skills']} skills → {out_dir}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
