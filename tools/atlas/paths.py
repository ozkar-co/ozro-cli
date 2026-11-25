"""GRF path helpers — port of tools/grf/lib/paths.js."""

from __future__ import annotations

UI_TEXTURE = "data/texture/유저인터페이스"
MOB_SPRITE_DIR = "data/sprite/몬스터"
MOB_SPRITE_DIR_EN = "data/sprite/monster"
NPC_SPRITE_DIRS = (
    "data/sprite/npc",
    "data/sprite/엔피씨",
    "data/sprite/몬스터",
)


def item_icon_path(resource_name: str) -> str:
    return f"{UI_TEXTURE}/item/{resource_name}.bmp"


def item_illustration_path(resource_name: str) -> str:
    return f"{UI_TEXTURE}/collection/{resource_name}.bmp"


def skill_icon_path(resource_name: str) -> str:
    """Skill icons live in the same UI item folder as item icons."""
    return item_icon_path(resource_name)


def map_minimap_candidates(map_stem: str) -> list[str]:
    """Client minimap BMPs under UI texture/map (textured overview)."""
    stem = map_stem.strip()
    if not stem:
        return []
    # Prefer exact stem, then common p-prefix / lowercase variants.
    stems = [stem, stem.lower()]
    if not stem.startswith("p"):
        stems.append(f"p{stem}")
        stems.append(f"p{stem.lower()}")
    seen: set[str] = set()
    out: list[str] = []
    for name in stems:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{UI_TEXTURE}/map/{name}.bmp")
    return out


def mob_sprite_candidates(aegis_name: str, sprite_name: str | None) -> list[str]:
    base = aegis_name.lower()
    candidates: list[str] = []
    if sprite_name:
        stem = sprite_name
        if stem.lower().endswith((".gr2", ".spr", ".act")):
            stem = stem.rsplit(".", 1)[0]
        for folder in (MOB_SPRITE_DIR, MOB_SPRITE_DIR_EN):
            candidates.append(f"{folder}/{stem}.spr")
    candidates.extend(
        [
            f"{MOB_SPRITE_DIR}/{base}.spr",
            f"{MOB_SPRITE_DIR}/{aegis_name}.spr",
            f"{MOB_SPRITE_DIR}/{base}_1.spr",
            f"{MOB_SPRITE_DIR}/1_{base}.spr",
            f"{MOB_SPRITE_DIR_EN}/{base}.spr",
        ]
    )
    # preserve order, unique
    seen: set[str] = set()
    out: list[str] = []
    for path in candidates:
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def npc_sprite_candidates(sprite_name: str) -> list[str]:
    stem = sprite_name
    if stem.lower().endswith((".gr2", ".spr", ".act")):
        stem = stem.rsplit(".", 1)[0]
    out: list[str] = []
    for folder in NPC_SPRITE_DIRS:
        out.append(f"{folder}/{stem}.spr")
    return out


def act_path_for_spr(spr_path: str) -> str:
    if spr_path.lower().endswith(".spr"):
        return spr_path[:-4] + ".act"
    return spr_path + ".act"
