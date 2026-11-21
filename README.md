# OzRo Client

Parche de cliente de Ragnarok Online para **OzRagnarok** (3 jugadores). Se mantiene a mano, sin updater ni servicios web. Se edita `patch/`, se comprime en `dist/patch.zip` y se reparte por USB o link; cada jugador lo descomprime en la raíz de su cliente. Sitio informativo: `https://ro.ozkr.net/`.

## Docs

- `docs/client-assets.md` — carpetas, tipos de archivo y cableado (mapas/alias, items, mobs/NPCs identity+jobname, ACT→wav, inventario).
- `docs/ragexe-internals.md` — parches del `OzRo.exe`.

## Estructura

```
patch/
  OzRo.exe
  data.ini
  ozro_fix.grf      capa de fixes: loading/sprites (prioridad 1)
  ozro.grf          base custom: data/ + System/ (prioridad 2)
  gefenia.grf       mapas custom
  System/           Lua que el cliente abre desde disco
  data/             msgstringtable + Lua de UI
  OzRo.ico, Setup.exe, mfc100.dll
dist/patch.zip      paquete manual para repartir
tools/grf.py        lector/extractor GRF v2
tools/grf_pack.py   empaquetador GRF v2
tools/restore_loose.py  materializa la capa Lua desde el GRF
tmp/                pruebas y GRFs locales (ignorado por git)
```

`ozro.grf` y `ozro_fix.grf` son la fuente canónica. `patch/System/` y `patch/data/`
tienen la capa mínima que el Lua VM abre con `io.open`/`dofile`; no es opcional para
el cliente web. `data.ini` ordena de mayor a menor prioridad (clave 1 gana) y
`rdata.grf` va antes que `data.grf` porque es renewal y pisa algunas entradas.
Un fix futuro es un GRF nuevo en la clave 1 más el `data.ini`; el `.exe` solo se
toca en casos extremos. Después de tocar el GRF, corré `restore_loose.py` para
mantener la paridad de `patch/System/` y `patch/data/`.

## Items

- `System/itemInfo_EN.lua` existe en `patch/System/` (loose, para el Lua VM) y dentro de `patch/ozro.grf` (fuente canónica). Editar `patch/System/itemInfo_EN.lua` dentro de `tbl`.
- Al publicar, empaquetarlo en un fix GRF y correr `tools/restore_loose.py` para que el loose y el GRF queden en paridad.
- Encoding mixto: texto visible en **ISO-8859-1/CP1252**; `ResourceName` vanilla en **CP949**; custom en ASCII (`ozro_*`).
- Abrir y guardar el archivo como **ISO-8859-1 estricto** (no UTF-8 ni autodetectado). Los `ResourceName` coreanos se ven como mojibake y no se tocan. Comparar con `cmp` contra la extracción original para confirmar que no se corrompió.
- Para añadir o corregir un item: editar `patch/System/itemInfo_EN.lua`, empaquetar `System/` e icono/collection en `patch/ozro_fix.grf` (o un fix nuevo) con `tools/grf_pack.py` y ponerlo como clave 1 en `data.ini`. Los BMP van en `data/texture/유저인터페이스/item|collection/<resource>.bmp`; alta en `rathena/db/import/item_db.yml` (fuera de este repo), probar con `@reloaditemdb` y `@item`, y repackear.
- `grf_pack.py` normaliza nombres de archivo mal codificados (UTF-8 de mojibake) a los bytes CP949 que espera el cliente.
- Si el `ResourceName` es custom y falta el BMP de item o collection, el cliente muestra `Resource File Loading fail`.

## Quests y CTRL+U

- El server define las quests en `rathena/db/import/quest_db.yml` y en los scripts (`setquest`/`setquestinfo`).
- El cliente muestra la ventana CTRL+U desde `patch/System/OngoingQuestInfoList_True_EN.lub` (y variantes `_EN`/`_True`), también dentro de `patch/ozro.grf`; el GRF es la fuente canónica y el loose es la copia que usa el Lua VM. **Cada QuestID debe existir en ambos lados**: si falta en el cliente, la quest aparece vacía/rota aunque el server la tenga.
- Bounty boards: `F_Bounty_Board` recibe cuartetos `MonsterID, QuestID, BaseExp, JobExp`; cada `QuestID` tiene que estar en `quest_db.yml` y en la lista del cliente.
- Estado actual: los 290 IDs custom de `quest_db.yml` (incluidas las bounty boards) están presentes en la lista del cliente.
- `npc/custom/ozro/hunting_missions.txt` (Hunting Missions, Euphy) está deshabilitado en `scripts_custom.conf`. Usa variables de personaje (`Mission0`, `#Mission_Delay`), **no** el sistema de quests, así que no afecta CTRL+U.
- En `npc/custom/ozro/bounty/Geffen.txt` están comentados `FAKE_ANGEL` (1371/62691) y `MINI_DEMON` (1292/62693). Ambos IDs existen hoy en `quest_db.yml` y en la lista del cliente; se pueden reactivar y probar.
- Al crear una quest custom: alta en `quest_db.yml`, entrada en la lista del cliente, y prueba en CTRL+U. `DISABLE_QUESTINFO_MARKERS` solo oculta el icono de questinfo sobre el NPC, no la ventana de quests.

## Mapas sin árboles de navidad

El `data.grf` actual trae versiones de evento en varias ciudades. Los overrides no-event viven en `patch/ozro.grf` (clave 1 de `data.ini`):

| Mapa | `.rsw` (modelos) | `.gnd` (piso/sombras) |
|---|---|---|
| `prontera` | `pprontera.rsw` del mismo `data.grf` | `pprontera.gnd` |
| `geffen`, `izlude`, `aldebaran`, `alberta`, `hugel` | `Ragnarok_210607/data.grf` | el `.gnd` de la misma fuente |

- El `.rsw` quita árboles y decoración; el `.gnd` aporta las texturas de piso y los lightmaps con las sombras horneadas. Si se cambia solo el `.rsw`, quedan las sombras del mapa de evento (árboles que ya no están).
- No se reemplaza el `.gat`: la colisión y el `map_cache` del server no cambian.
- Los `.rsw` de las 5 ciudades coinciden byte a byte con `Ragnarok_210607/data.grf`, así que su `.gnd` es el par correcto.
- Para revertir un mapa: quitar sus entradas del GRF y reempaquetar.
- Izlude conserva 4 modelos pequeños de pan navideño, no árboles; el resto de las ciudades quedó sin referencias navideñas.
- Otras ciudades: Rachel/Malangdo/Lasagna tienen referencias menores; Payon, Lighthalzen, Einbroch, Veins, Umbala, etc. tienen el RSW cifrado y no se escanearon.
- Si el cliente muestra modelos faltantes o NPCs desalineados, probar el set GND/RSW completo de la misma fuente o revertir ese mapa puntual.

## Imágenes (genkit, externo)

Herramienta: `/home/oz/Code/genkit` (perfiles YAML + Replicate/RunPod). Perfiles RO:

- `ro-item-icon`: RD+ `skill_icon`, genera 96×96 y deja BMP **24×24, 8bpp, fondo magenta**.
- `ro-item-illustration`: RunPod Flux Schnell, genera 512×688 y deja BMP **75×100, 24bpp, fondo blanco**.

Flujo recomendado: **3 variantes de icono y 3 de ilustración por item, con seed random**, armar una overview y que el usuario elija. No elegir automáticamente.

```bash
cd /home/oz/Code/genkit
./run.sh image --profile ro-item-icon --prompt "..." --out /ruta/item/<resource>.bmp
./run.sh image --profile ro-item-illustration --prompt "..." --out /ruta/collection/<resource>.bmp
```

Preferencias de estilo:

- Iconos: pixel art RO, silueta clara, 1px de outline, sin texto.
- Ilustraciones: acuarela/lápiz de color, ligera inclinación en tres cuartos, sombra suave separada del objeto, fondo blanco.
- Los perfiles hacen el postproceso local con Pillow; `--out` debe terminar en `.bmp`.

## GRF

`tools/grf.py` lee GRF v2, lista y extrae. `tools/grf_pack.py` empaqueta GRF v2:

```bash
python3 tools/grf_pack.py --out patch/ozro_fix_YYYYMMDD.grf \
  --root data=/ruta/data --root System=/ruta/System
```

Empaquetar un fix nuevo y ponerlo como clave 1 en `data.ini` evita tocar `ozro.grf`. El empaquetador normaliza cada componente de ruta a CP949.

```bash
python3 tools/grf.py info tmp/rdata.grf
python3 tools/grf.py list tmp/rdata.grf --filter collection --limit 20
python3 tools/grf.py extract tmp/rdata.grf "data/texture/.../collection/amber.bmp" --out /tmp/amber.bmp
python3 tools/grf.py extract-matching tmp/rdata.grf --filter .gat --out-dir /tmp/gat --limit 3
```

Los mapas `.gat`/`.rsw`/`.gnd` de rdata son plaintext. La única entrada DES se reporta como no soportada.

## Archivos sueltos para el cliente web

El GRF es la fuente canónica, pero roBrowser ejecuta Lua con `io.open`/`dofile`
y esos archivos tienen que existir en disco. Si faltan aparecen `Unknown Item`,
`QuestInfoList` nil y errores de `Towninfo`/`msgstringtable`.

`patch/System/` y `patch/data/` ya contienen esa capa. Para materializarla también
en la carpeta del cliente:

```bash
python3 tools/restore_loose.py --grf patch/ozro.grf --out "/mnt/games/OzRo"
```

El script extrae:

- `System/itemInfo_EN.lua`
- `System/OngoingQuestInfoList_True_EN.lub`
- `System/Towninfo.lub` y `System/Towninfo_EN.lub`
- `data/msgstringtable.txt`
- `data/luafiles514/lua files/signboardlist.lub`
- `data/luafiles514/lua files/datainfo/tb_cashshop_banner.lub`

El compose del cliente web monta `System/` y `data/` en `/app/System` y
`/app/data`, así que el Lua VM los encuentra ahí.

## Enviar cambios

1. Extraer, editar y reempaquetar el GRF correspondiente en `patch/`, y probar.
2. Comprimir el contenido de `patch/` en `dist/patch.zip`.
3. Repartir por USB o link; descomprimir en la raíz del cliente.
