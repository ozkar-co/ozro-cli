# Cliente RO — assets, carpetas y cableado

Last verified: 2026-11-21  
Audience: agentes / ops de OzRo.  
Scope: stack activo `patch/data.ini` → `ozro.grf` ≻ `data.grf`.  
Inventario machine-readable: `tools/export_client_inventory.py` → `ozro-data/reports/client_*.jsonl`.

## Stack y prioridad

`data.ini` (clave menor gana). El cliente abre el **primer** path que exista en ese orden.

| Pri | Archivo | Rol |
|---:|---|---|
| 1 | `patch/ozro.grf` | parche OzRo (fuente canónica de overrides) |
| 2 | `tmp/data.grf` (o `data.grf` del cliente) | base kRO |

- Paths case-insensitive en GRF; stems suelen compararse en lower.
- Encoding: paths/UI coreanos **CP949**; `itemInfo_EN.lua` texto visible ISO-8859-1; ResourceName vanilla CP949 / custom ASCII.
- Lua que el VM abre con `io.open` debe existir **loose** bajo `patch/System/` o `patch/data/` además del GRF (`tools/restore_loose.py`).

## Mapa mental por dominio

```
MAPAS     resnametable? → data/<stem>.{rsw,gat,gnd} (+ minimap)
ITEMS     itemInfo[id].identifiedResourceName → icon/collection/sprite
MOB/NPC   classId → npcidentity JT_* → jobname sprite → spr+act | .gr2
SONIDO    .act embebe nombres .wav → data/wav/**
```

---

## Mapas

### Archivos

| Ext | Path típico | Función |
|---|---|---|
| `.rsw` | `data/<stem>.rsw` | modelos / escena |
| `.gat` | `data/<stem>.gat` | colisión (server `map_cache` alineado) |
| `.gnd` | `data/<stem>.gnd` | terreno / lightmaps |
| minimap | `data/texture/.../map/<stem>.*` | UI |

Un mapa “completo” en inventario = rsw+gat+gnd presentes (tras resolver alias).

### Alias — `data/resnametable.txt`

Líneas: `alias.ext#target.ext#`

El cliente puede pedir `airplane_01.rsw` y cargar `airplane.rsw`. **Sin leer resnametable, el inventario marca falso negativo.**

`export_client_inventory` resuelve alias y marca `alias_of` / `complete`.

Regla OzRo: no tocar `data.grf` base; overrides en `ozro.grf`. Alias PVP/BG fuera de restore masivo (ver historial maps).

---

## Items

### Resolución (no es el item id)

```
item id → System/itemInfo_EN.lua [id]
        → identifiedResourceName = "<stem>"
        → data/texture/유저인터페이스/item/<stem>.bmp
        → data/texture/유저인터페이스/collection/<stem>.bmp
        → data/sprite/아이템/<stem>.{spr,act}
```

- **Nunca** matchear `unidentifiedResourceName` al pedir `identified*` (lookbehind en el parser).
- Varios items pueden compartir el **mismo** ResourceName → mismo icono/sprite (normal).
- `slotCount` / View de headgear: además hace falta cableado en `accessoryid` / `accname` + sprites bajo `data/sprite/악세사리/...` o el equip falla aunque el icono exista.
- Card BMP: `data/texture/유저인터페이스/cardbmp/` (cosmético; no bloquea uso del item).

### Gaps útiles

| Reason | Significado |
|---|---|
| `no_iteminfo` | id de server sin bloque en itemInfo |
| `missing_assets` | itemInfo ok pero falta icon y/o spr+act |

Gap-fill: solo sets **completos** (icon+collection+spr+act) desde donor; append itemInfo **dentro** de `tbl = { ... }`.

---

## Mobs y NPCs — el cableado

El server manda un **número** (class / view id). El cliente **no** recibe el nombre de archivo.

```
classId
  → npcidentity.lub   JT_FOO = 12345
  → jobname.lub       [jobtbl.JT_FOO] = "sprite_stem"   # o "foo.gr2"
  → archivos
       data/sprite/몬스터/<stem>.{spr,act}     # mobs
       data/sprite/monster/<stem>.{spr,act}    # alias EN raro
       data/sprite/npc/<stem>.{spr,act}        # NPCs (también 엔피씨)
       data/**/<stem>.gr2                      # guardians, cajas, emperium, …
```

| Pieza | Archivo (prioridad GRF) | Rol |
|---|---|---|
| Identity | `data/luafiles514/lua files/datainfo/npcidentity.lub` | id ↔ `JT_*` |
| Jobname | `data/luafiles514/lua files/datainfo/jobname.lub` | `JT_*` ↔ stem |
| Sprite | carpeta mob/npc o `.gr2` | pixels + animación |

### Implicaciones

- **Archivo sin identity/jobname** = biblioteca muerta: `@disguise` / script no pueden pedirlo.
- **Identity/jobname sin spr** = popup `Spr :: Cannot find File`.
- Varios `JT_*` pueden apuntar al **mismo** stem (alias de sprite; match case-insensitive).
- Server rAthena: constantes `JT_*` / `4_F_KAFRA1` en `npc.hpp` + `script_constants.hpp`. El id del enum debe **coincidir** con `npcidentity` del cliente.
- Scripts NPC: `map,x,y,dir script Name 4_ALEXSANDER,{ ... }` o el id numérico.

### Inventario OzRo

- **Mobs:** cruce `mob_db` ↔ identity ↔ jobname ↔ spr/act|gr2 → `client_mob_server_gaps.jsonl`.
- **NPCs (schema ≥6):** `client_npc_sprites.jsonl` lista solo stems **referenciados por jobname** (usables). Meta: `npc_sprites_files` / `npc_sprites_unwired` para lo suelto en GRF.
- **NPCs (schema ≥8):** cada fila incluye `sprite_ids` (ints de `npcidentity`) y `jt_names` para join directo desde headers de script (`sprite_id` numérico).

Reasons mob gap: `no_identity` | `no_jobname` | `missing_sprite`.

---

## Sprites `.spr` + `.act`

| Archivo | Qué es |
|---|---|
| `.spr` | frames / atlas |
| `.act` | animaciones (idle/walk/atk/die) + **eventos de sonido** |

No hay “paquete de animación” aparte: sin `.act` no hay anim usable. Gap-fill siempre **spr+act juntos**.

### Sonidos desde el ACT

Los `.act` guardan nombres `.wav` **null-terminated** (pueden tener espacios, ej. `cru_holy cross.wav`).

```
data/wav/<name>.wav
data/wav/effect/...   # a veces skills
```

Si falta el wav → popup `Wave :: Cannot find File` (el mob/NPC igual puede verse).

`export_client_inventory` (schema ≥4/5) parsea ACT→wav y escribe `client_mob_act_gaps.jsonl` / `client_npc_act_gaps.jsonl`.

Notas:

- Algunos ACT oficiales traen strings truncados (`tep2.wav`, `amage.wav`) → placeholders silenciosos en `ozro.grf` si hace falta estabilidad.
- `spore_move.wav` referenciado pero solo existen `spore_move1/2` (a veces cifrados en GRF) → alias/placeholder.
- Skills de mob: FX suelen ser assets de skill compartidos, no del stem del mob.

---

## `.gr2` (3D)

Usado por guardians, treasure boxes, emperium, flags, etc. Jobname termina en `.gr2`; el inventario acepta stem presente en cualquier `data/**/*.gr2` como “sprite ok”.

---

## Carpetas sprite / texture (cheatsheet)

| Dominio | Paths |
|---|---|
| Item icon | `data/texture/유저인터페이스/item/` |
| Item collection | `data/texture/유저인터페이스/collection/` |
| Card | `data/texture/유저인터페이스/cardbmp/` |
| Item body sprite | `data/sprite/아이템/` |
| Mob | `data/sprite/몬스터/` (+ `monster/`) |
| NPC | `data/sprite/npc/` (+ `엔피씨/`) |
| Accessory | `data/sprite/악세사리/{남,여,...}/` |
| Wav | `data/wav/`, `data/wav/effect/` |
| Maps | `data/*.{rsw,gat,gnd}` |
| Lub datainfo | `data/luafiles514/lua files/datainfo/` |

---

## Relaciones que se repiten

| Relación | Ejemplo |
|---|---|
| N items → 1 ResourceName | mismos bmp/spr |
| N JT_* → 1 stem | varios mobs/NPCs reusan sprite |
| 1 stem → N wav | ACT lista attack/die/move… |
| Alias mapa → stem real | resnametable |
| Server AegisName ↛ sprite | mob_db no trae SpriteName; manda el id |

---

## Herramienta de inventario

```bash
python3 tools/export_client_inventory.py \
  --cli-root . --out-dir ../ozro-data/reports --rathena ../rathena
```

Salidas clave:

| Report | Contenido |
|---|---|
| `client_grf_index_meta.json` | schema + counts |
| `client_maps.jsonl` | mapas + alias + complete |
| `client_item_*.jsonl` | icons/sprites/itemInfo/server gaps |
| `client_mob_*.jsonl` | sprites, server gaps, ACT wav gaps |
| `client_npc_*.jsonl` | sprites **wired**, ACT wav gaps |

Gap-fill donor (kRO) = scripts one-shot bajo `.tmp/*_donor_fill/` (no tools permanentes): pack spr/act/wav + append texto a identity/jobname/itemInfo; no pisar `data.grf`.

### Checklist al añadir contenido

1. ¿Existe el archivo (spr+act o gr2 / bmp)?  
2. ¿Quién lo nombra (itemInfo / jobname / resnametable)?  
3. ¿El id del server coincide con identity?  
4. ¿El ACT pide wavs que existan?  
5. Re-export inventory y mirar `*_gaps.jsonl`.

---

## Referencias vivas

- Conteos / smoke: `rathena/docs/ozro-market/historia/brief-02/client_assets_inventory.md`
- Master dataset server: `rathena/docs/ozro-market/historia/brief-02/master_dataset.md`
- Internals exe: `docs/ragexe-internals.md`
