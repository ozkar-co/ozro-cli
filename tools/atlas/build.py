"""Build web atlases with alias dedup (resource/stem → one packed image)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .act import compose_idle_rgba, parse_act
from .bmp import bmp_to_image, normalize_icon
from .grf_stack import GrfStack, default_grf_paths
from .iteminfo import parse_iteminfo
from .jobname import load_jobname_resolver
from .mobdb import parse_mob_db
from .pack import pack_icon_atlases, pack_variable_atlases
from .paths import (
    act_path_for_spr,
    item_icon_path,
    item_illustration_path,
    mob_sprite_candidates,
    npc_sprite_candidates,
    skill_icon_path,
)
from .skillinfo import load_skill_entries
from .spr import parse_spr


@dataclass
class BuildReport:
    generated_at: str
    grfs: list[str] = field(default_factory=list)
    items_icons: dict = field(default_factory=dict)
    items_illustrations: dict = field(default_factory=dict)
    skills_icons: dict = field(default_factory=dict)
    mobs: dict = field(default_factory=dict)
    npcs: dict = field(default_factory=dict)


def build_web_atlases(
    *,
    cli_root: Path,
    out_dir: Path,
    client_dir: Path | None = None,
    iteminfo_path: Path | None = None,
    mob_db_paths: list[Path] | None = None,
    domains: set[str] | None = None,
    limit: int | None = None,
    overrides_dir: Path | None = None,
) -> dict:
    domains = domains or {"items", "mobs", "npcs", "skills"}
    out_dir.mkdir(parents=True, exist_ok=True)

    grf_paths = default_grf_paths(cli_root, client_dir)
    if not grf_paths:
        raise FileNotFoundError("No GRF files found (patch/ + tmp/ or --client-dir)")
    print(f"GRF stack ({len(grf_paths)}): " + ", ".join(p.name for p in grf_paths))
    stack = GrfStack(grf_paths)

    report = BuildReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        grfs=[p.name for p in grf_paths],
    )
    alias_maps: dict[str, dict] = {}
    # Preserve sibling domains when rebuilding a subset into an existing out_dir.
    existing_manifest: dict = {}
    existing_alias: dict = {}
    manifest_path = out_dir / "manifest.json"
    alias_path = out_dir / "alias-map.json"
    if manifest_path.is_file():
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_manifest = {}
    if alias_path.is_file():
        try:
            existing_alias = json.loads(alias_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_alias = {}

    manifest: dict = {
        "version": 2,
        "generatedAt": report.generated_at,
        "items": existing_manifest.get("items")
        or {"icons": {"pages": []}, "illustrations": {"pages": []}},
        "skills": existing_manifest.get("skills") or {"icons": {"pages": []}},
        "mobs": existing_manifest.get("mobs") or {"sprites": {"pages": []}},
        "npcs": existing_manifest.get("npcs") or {"sprites": {"pages": []}},
    }
    if isinstance(existing_alias, dict):
        alias_maps.update(existing_alias)

    if "items" in domains:
        iteminfo = iteminfo_path or _find_iteminfo(cli_root, client_dir)
        if not iteminfo or not iteminfo.is_file():
            raise FileNotFoundError("itemInfo_EN.lua / itemInfo.lua not found")
        print(f"Parsing itemInfo: {iteminfo}")
        items = parse_iteminfo(iteminfo)
        entries = list(items.items())
        if limit:
            entries = entries[:limit]
        print(f"  {len(items)} items ({len(entries)} to process)")

        icons_unique: dict[str, Image.Image] = {}
        icons_id_to_key: dict[str, str] = {}
        illust_unique: dict[str, Image.Image] = {}
        illust_id_to_key: dict[str, str] = {}
        icon_ok = icon_miss = illust_ok = illust_miss = 0
        resource_alias: dict[str, list[int]] = {}

        for item_id, entry in entries:
            resource = entry.resource_name
            if not resource:
                icon_miss += 1
                illust_miss += 1
                continue
            key = resource.lower()
            resource_alias.setdefault(key, []).append(item_id)

            if key not in icons_unique:
                raw = stack.read(item_icon_path(resource))
                if raw:
                    try:
                        icons_unique[key] = normalize_icon(raw)
                        icon_ok += 1
                    except Exception:
                        icon_miss += 1
                else:
                    icon_miss += 1
            if key in icons_unique:
                icons_id_to_key[str(item_id)] = key

            if key not in illust_unique:
                raw = stack.read(item_illustration_path(resource))
                if raw:
                    try:
                        illust_unique[key] = bmp_to_image(raw)
                        illust_ok += 1
                    except Exception:
                        illust_miss += 1
                else:
                    illust_miss += 1
            if key in illust_unique:
                illust_id_to_key[str(item_id)] = key

        print(
            f"  icons: {len(icons_unique)} unique / {len(icons_id_to_key)} ids "
            f"(decoded {icon_ok}, miss {icon_miss})"
        )
        print(
            f"  illustrations: {len(illust_unique)} unique / {len(illust_id_to_key)} ids "
            f"(decoded {illust_ok}, miss {illust_miss})"
        )

        icon_pages = pack_icon_atlases(
            icons_unique, icons_id_to_key, out_dir / "items" / "icons"
        )
        illust_pages = pack_variable_atlases(
            illust_unique, illust_id_to_key, out_dir / "items" / "illustrations"
        )
        manifest["items"]["icons"]["pages"] = [
            _page_manifest(p, "items/icons") for p in icon_pages
        ]
        manifest["items"]["illustrations"]["pages"] = [
            _page_manifest(p, "items/illustrations") for p in illust_pages
        ]
        report.items_icons = {
            "unique": len(icons_unique),
            "ids": len(icons_id_to_key),
            "miss": icon_miss,
        }
        report.items_illustrations = {
            "unique": len(illust_unique),
            "ids": len(illust_id_to_key),
            "miss": illust_miss,
        }
        alias_maps["items"] = {
            "by_resource": {
                k: ids for k, ids in resource_alias.items() if len(ids) > 1
            },
            "id_to_resource": {str(i): e.resource_name for i, e in entries if e.resource_name},
        }

    if "skills" in domains:
        print("Parsing skillid / skillinfolist…")
        skills = load_skill_entries(stack)
        if limit:
            skills = skills[:limit]
        print(f"  {len(skills)} skills to process")

        icons_unique: dict[str, Image.Image] = {}
        icons_id_to_key: dict[str, str] = {}
        icon_ok = icon_miss = 0
        resource_alias: dict[str, list[int]] = {}

        for entry in skills:
            resource = entry.resource_name
            if not resource:
                icon_miss += 1
                continue
            key = resource.lower()
            resource_alias.setdefault(key, []).append(entry.skill_id)

            if key not in icons_unique:
                raw = stack.read(skill_icon_path(resource))
                if not raw and resource != resource.lower():
                    raw = stack.read(skill_icon_path(resource.lower()))
                if raw:
                    try:
                        icons_unique[key] = normalize_icon(raw)
                        icon_ok += 1
                    except Exception:
                        icon_miss += 1
                else:
                    icon_miss += 1
            if key in icons_unique:
                icons_id_to_key[str(entry.skill_id)] = key

        print(
            f"  skill icons: {len(icons_unique)} unique / {len(icons_id_to_key)} ids "
            f"(decoded {icon_ok}, miss {icon_miss})"
        )
        skills_out = out_dir / "skills" / "icons"
        if skills_out.is_dir():
            for stale in skills_out.iterdir():
                if stale.suffix.lower() in {".webp", ".json"}:
                    stale.unlink()
        icon_pages = pack_icon_atlases(
            icons_unique, icons_id_to_key, skills_out
        )
        manifest["skills"]["icons"]["pages"] = [
            _page_manifest(p, "skills/icons") for p in icon_pages
        ]
        report.skills_icons = {
            "unique": len(icons_unique),
            "ids": len(icons_id_to_key),
            "miss": icon_miss,
        }
        alias_maps["skills"] = {
            "by_resource": {
                k: ids for k, ids in resource_alias.items() if len(ids) > 1
            },
            "id_to_resource": {
                str(e.skill_id): e.resource_name for e in skills if e.resource_name
            },
            "id_to_aegis": {str(e.skill_id): e.aegis_name for e in skills},
        }

    if "mobs" in domains or "npcs" in domains:
        jobnames = load_jobname_resolver(stack)
        print(
            f"jobname: {len(jobnames.id_to_const)} ids, "
            f"{len(jobnames.const_to_sprite)} sprites"
        )

    if "mobs" in domains:
        mob_paths = mob_db_paths or [
            cli_root.parent / "rathena" / "db" / "re" / "mob_db.yml",
            cli_root.parent / "rathena" / "db" / "import" / "mob_db.yml",
        ]
        mobs = parse_mob_db(mob_paths)
        if limit:
            mobs = mobs[:limit]
        print(f"mobs: {len(mobs)} from mob_db")

        unique: dict[str, Image.Image] = {}
        id_to_key: dict[str, str] = {}
        stem_alias: dict[str, list[int]] = {}
        ok = miss = gr2 = 0
        miss_list: list[dict] = []

        for mob in mobs:
            sprite_name = jobnames.sprite_name_for_id(mob.mob_id)
            stem = jobnames.stem_for_id(mob.mob_id)
            if sprite_name and sprite_name.lower().endswith(".gr2"):
                gr2 += 1
            key = (stem or mob.aegis_name or str(mob.mob_id)).lower()
            stem_alias.setdefault(key, []).append(mob.mob_id)

            if key not in unique:
                img = _load_sprite_image(stack, mob_sprite_candidates(mob.aegis_name, sprite_name))
                if img is None:
                    miss += 1
                    miss_list.append(
                        {
                            "id": mob.mob_id,
                            "aegis": mob.aegis_name,
                            "sprite": sprite_name,
                        }
                    )
                else:
                    # Fit large previews for atlas density
                    img = _fit_inside(img, 160, 160)
                    unique[key] = img
                    ok += 1
            if key in unique:
                id_to_key[str(mob.mob_id)] = key

        # Overrides for .gr2 / missing (same semantics as old builder)
        overrides = overrides_dir or (cli_root / "data" / "overrides" / "mobs")
        override_n = _apply_mob_overrides(overrides, mobs, jobnames, unique, id_to_key)
        if override_n:
            print(f"  mob overrides applied: {override_n}")

        print(f"  sprites: {len(unique)} unique / {len(id_to_key)} ids (ok stems {ok}, miss {miss}, gr2 refs {gr2})")
        pages = pack_variable_atlases(unique, id_to_key, out_dir / "mobs" / "sprites")
        manifest["mobs"]["sprites"]["pages"] = [
            _page_manifest(p, "mobs/sprites") for p in pages
        ]
        report.mobs = {
            "unique": len(unique),
            "ids": len(id_to_key),
            "miss": miss,
            "gr2_refs": gr2,
            "overrides": override_n,
            "miss_sample": miss_list[:50],
        }
        alias_maps["mobs"] = {
            "by_stem": {k: ids for k, ids in stem_alias.items() if len(ids) > 1},
            "id_to_stem": {
                str(m.mob_id): (jobnames.stem_for_id(m.mob_id) or m.aegis_name)
                for m in mobs
            },
        }

    if "npcs" in domains:
        # All jobname stems that look like NPCs (4_*, etc.) + every const
        npc_unique: dict[str, Image.Image] = {}
        npc_id_to_key: dict[str, str] = {}
        stem_to_ids: dict[str, list[int]] = {}
        for class_id, const in jobnames.id_to_const.items():
            sprite = jobnames.const_to_sprite.get(const)
            if not sprite or sprite.lower().endswith(".gr2"):
                continue
            stem = jobnames.stem_for_id(class_id)
            if not stem:
                continue
            key = stem.lower()
            stem_to_ids.setdefault(key, []).append(class_id)
            if limit and len(npc_unique) >= limit and key not in npc_unique:
                continue
            if key not in npc_unique:
                img = _load_sprite_image(stack, npc_sprite_candidates(stem))
                if img is None:
                    continue
                npc_unique[key] = _fit_inside(img, 160, 160)
            if key in npc_unique:
                npc_id_to_key[str(class_id)] = key
                # also index by stem name for NPC scripts that use the string key
                npc_id_to_key[stem] = key
                npc_id_to_key[stem.lower()] = key

        print(f"npcs: {len(npc_unique)} unique / {len(npc_id_to_key)} keys")
        pages = pack_variable_atlases(npc_unique, npc_id_to_key, out_dir / "npcs" / "sprites")
        # Also write a flat index.json compatible with the old NPC gif index shape
        npc_index = {
            key: {
                "atlas": True,
                "stem": key,
            }
            for key in npc_unique
        }
        npc_dir = out_dir / "npcs" / "sprites"
        npc_dir.mkdir(parents=True, exist_ok=True)
        (npc_dir / "index.json").write_text(
            json.dumps(
                {
                    "generatedAt": report.generated_at,
                    "source": "ozro-cli/tools/atlas (GRF spr+act)",
                    "count": len(npc_unique),
                    "keys": sorted(npc_unique.keys()),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest["npcs"]["sprites"]["pages"] = [
            _page_manifest(p, "npcs/sprites") for p in pages
        ]
        report.npcs = {"unique": len(npc_unique), "keys": len(npc_id_to_key)}
        alias_maps["npcs"] = {
            "by_stem": {k: ids for k, ids in stem_to_ids.items() if len(ids) > 1}
        }

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "alias-map.json").write_text(
        json.dumps(alias_maps, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "build-report.json").write_text(
        json.dumps(report.__dict__, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out_dir / 'manifest.json'}")
    return {"manifest": manifest, "report": report.__dict__, "out_dir": str(out_dir)}


def _page_manifest(page, base: str) -> dict:
    return {
        "page": page.page,
        "image": f"{base}/{page.image}",
        "mapping": f"{base}/{page.mapping}",
        "count": page.count,
        "width": page.width,
        "height": page.height,
    }


def _find_iteminfo(cli_root: Path, client_dir: Path | None) -> Path | None:
    candidates = [
        cli_root / "patch" / "System" / "itemInfo_EN.lua",
        cli_root / "patch" / "System" / "itemInfo.lua",
    ]
    if client_dir:
        candidates.extend(
            [
                client_dir / "System" / "itemInfo_EN.lua",
                client_dir / "System" / "itemInfo.lua",
            ]
        )
    # also site copy
    candidates.append(cli_root.parent / "ozro-site" / "data" / "itemInfo_EN.lua")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _load_sprite_image(stack: GrfStack, candidates: list[str]) -> Image.Image | None:
    for spr_path in candidates:
        raw = stack.read(spr_path)
        if not raw:
            continue
        try:
            spr = parse_spr(raw)
        except Exception:
            continue
        act = None
        act_raw = stack.read(act_path_for_spr(spr_path))
        if act_raw:
            try:
                act = parse_act(act_raw)
            except Exception:
                act = None
        composed = compose_idle_rgba(spr, act)
        if not composed:
            continue
        w, h, rgba = composed
        return Image.frombytes("RGBA", (w, h), rgba)
    return None


def _fit_inside(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    w, h = img.size
    if w <= max_w and h <= max_h:
        return img
    img = img.copy()
    img.thumbnail((max_w, max_h), Image.Resampling.NEAREST)
    return img


def _apply_mob_overrides(overrides_dir, mobs, jobnames, unique, id_to_key) -> int:
    if not overrides_dir or not Path(overrides_dir).is_dir():
        return 0
    covered = 0
    files = [p for p in Path(overrides_dir).iterdir() if p.suffix.lower() == ".png"]
    for path in files:
        key_name = path.stem.lower()
        try:
            img = Image.open(path).convert("RGBA")
            img = _fit_inside(img, 160, 160)
        except Exception as exc:
            print(f"  override skip {path.name}: {exc}")
            continue

        target_model = None
        explicit_id = key_name if re.fullmatch(r"\d+", key_name) else None
        if explicit_id:
            target_model = (jobnames.stem_for_id(int(explicit_id)) or "").lower() or None
        else:
            target_model = re.sub(r"\.(gr2|spr|act)$", "", key_name)

        targets: set[str] = set()
        if explicit_id:
            targets.add(explicit_id)
        if target_model:
            for mob in mobs:
                stem = (jobnames.stem_for_id(mob.mob_id) or "").lower()
                if stem == target_model:
                    targets.add(str(mob.mob_id))

        for mob_id in targets:
            # model key for packing
            model_key = target_model or f"override:{mob_id}"
            if model_key not in unique:
                unique[model_key] = img
            # only fill gaps — never replace a real sprite id mapping to an extracted stem
            if mob_id in id_to_key:
                continue
            id_to_key[mob_id] = model_key
            covered += 1
    return covered
