"""Parse skillid.lub + skillinfolist.lub from GRF bytes (no Lua exec)."""

from __future__ import annotations

import re
from dataclasses import dataclass


SKILLID_CANDIDATES = (
    "data/lua files/skillinfoz/skillid.lub",
    "data/luafiles514/lua files/skillinfoz/skillid.lub",
)

SKILLINFOLIST_CANDIDATES = (
    "data/lua files/skillinfoz/skillinfolist.lub",
    "data/luafiles514/lua files/skillinfoz/skillinfolist.lub",
)

_BLOCK_RE = re.compile(r"\[SKID\.(\w+)\]\s*=\s*\{(.*?)\n\t\},?", re.S)


@dataclass(frozen=True)
class SkillInfoEntry:
    skill_id: int
    aegis_name: str
    resource_name: str
    display_name: str | None


def parse_skillid(data: bytes) -> dict[str, int]:
    text = data.decode("utf-8", errors="replace")
    out: dict[str, int] = {}
    for m in re.finditer(r"(\w+)\s*=\s*(\d+)", text):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_skillinfolist(data: bytes) -> dict[str, dict]:
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
    out: dict[str, dict] = {}
    for m in _BLOCK_RE.finditer(text):
        sk = m.group(1)
        body = m.group(2)
        res_m = re.search(r'^\s*"((?:\\.|[^"\\])*)"', body, re.M)
        name_m = re.search(r'SkillName\s*=\s*"((?:\\.|[^"\\])*)"', body)
        out[sk] = {
            "resource_name": res_m.group(1) if res_m else sk,
            "display_name": name_m.group(1) if name_m else None,
        }
    return out


def _is_lua_bytecode(raw: bytes) -> bool:
    return raw.startswith(b"\x1bLua")


def load_skill_entries(stack) -> list[SkillInfoEntry]:
    """Read skill catalog from GRF stack → one entry per numeric id.

    Prefer plaintext .lub (older `data/lua files/...`). Some stacks ship
    compiled LuaQ bytecode under luafiles514 which we cannot parse here.
    """
    skill_ids: dict[str, int] = {}
    for path in SKILLID_CANDIDATES:
        raw = stack.read(path)
        if not raw or _is_lua_bytecode(raw):
            continue
        skill_ids = parse_skillid(raw)
        if skill_ids:
            break
    if not skill_ids:
        raise FileNotFoundError(
            "plaintext skillid.lub not found in GRF stack (bytecode-only copies skipped)"
        )

    info_by: dict[str, dict] = {}
    for path in SKILLINFOLIST_CANDIDATES:
        raw = stack.read(path)
        if not raw or _is_lua_bytecode(raw):
            continue
        info_by = parse_skillinfolist(raw)
        if info_by:
            break

    entries: list[SkillInfoEntry] = []
    for aegis, skill_id in skill_ids.items():
        info = info_by.get(aegis) or {}
        resource = info.get("resource_name") or aegis
        entries.append(
            SkillInfoEntry(
                skill_id=skill_id,
                aegis_name=aegis,
                resource_name=resource,
                display_name=info.get("display_name"),
            )
        )
    entries.sort(key=lambda e: e.skill_id)
    return entries
