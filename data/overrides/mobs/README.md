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

## Image guidelines

- Accepted formats: `.png`, `.gif`, `.webp`, `.jpg`. For animated `.gif`/`.webp`
  the builder uses the **first frame** (frame 0) and flattens it into the atlas.
- Prefer a transparent background (alpha or a transparent GIF index).
- Roughly square; the builder fits them inside 160x160.
- A tight crop of the entity looks best next to the 2D sprites.

## Current 3D models to cover

One image per row covers all the listed mobs (extension can be `.png`/`.gif`/`.webp`/`.jpg`):

| File to add | Entity | Model | Mobs covered |
|-------------|--------|-------|--------------|
| `1285.*`  | Archer Guardian  | `Aguardian90_8.gr2` | 4  |
| `1286.*`  | Knight Guardian  | `Kguardian90_7.gr2` | 4  |
| `1287.*`  | Soldier Guardian | `Sguardian90_9.gr2` | 1  |
| `1288.*`  | Emperium         | `Empelium90_0.gr2`  | 2  |
| `1324.*`  | Treasure Chest   | `TREASUREBOX_2.gr2` | 69 |

After adding the PNGs, run `npm run assets` from the `ozro-cli` root to rebuild.
