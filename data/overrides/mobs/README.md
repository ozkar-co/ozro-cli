# Mob sprite overrides

Some monsters use 3D models (Granny `.gr2`) instead of 2D `.spr` sprites, so the
GRF extractor can't turn them into images automatically. Drop manual PNGs here and
the asset builder (`npm run assets`) will merge them into the mob atlas.

## Naming

Name each PNG by either:

- a **representative mob id** — covers every mob that shares the same 3D model, or
- the **model name** (without extension) — same effect.

Overrides never replace a mob that already has a real extracted sprite; they only
fill in the gaps.

## PNG guidelines

- Transparent background (PNG with alpha).
- Roughly square; the builder fits them inside 160x160.
- A tight crop of the entity looks best next to the 2D sprites.

## Current 3D models

One PNG per model covers every mob that shares that `.gr2`. Present overrides:

| File | Entity | Model | Notes |
|------|--------|-------|-------|
| `1285.png` | Archer / Bow Guardian | `Aguardian90_8.gr2` | |
| `1949.png` | Knight / Sword Guardian | `Kguardian90_7.gr2` | also covers 1286, 1829, 1899 |
| `1287.png` | Soldier Guardian | `Sguardian90_9.gr2` | |
| `1288.png` | Emperium | `Empelium90_0.gr2` | also Dream Metal 1846 |
| `1903.png` | Treasure Chest | `TREASUREBOX_2.gr2` | many box ids |
| `722.png` | Guild Flag | `Guildflag90_1.gr2` | |

Still without override (left as miss → mob placeholder): Hugeling `1284`, Zombie Dragon `1181`.

Rebuild:

```bash
python3 tools/build_web_atlases.py --domains mobs --out tmp/web-assets-mobs
# then merge mobs/sprites + manifest/alias into ozro-site/assets
```
