# Instalación del cliente OzRo

El zip OzRo es un **overlay** sobre un cliente kRO completo. No incluye `data.grf` ni los GRF base (~4 GB).

## Contenido del zip OzRo

```
ozro.grf          # overlay (branding, IP, texturas custom)
data.ini          # orden de carga GRF
OzRo.exe          # exe parcheado para servidor privado
System/           # itemInfo custom (en disco, NO dentro del GRF)
  itemInfo_v5.lub
  itemInfo_v5.lua
```

## Primera instalación (jugador)

1. Descargar el **cliente kRO completo** (Google Drive / pack comunitario).
   Debe incluir al menos: `data.grf`, `renewal2021.grf`, `resources2021.grf`, `rdata.grf`.
2. Descomprimir el **zip OzRo** encima de la carpeta del cliente (sobrescribe/añade archivos).
   Debe crear/actualizar la carpeta `System/` junto al exe.
3. Ejecutar `OzRo.exe` desde esa carpeta.

## Actualización OzRo (mismo cliente base)

1. Descomprimir el zip nuevo **sobre la carpeta existente**.
2. Sobrescribe `ozro.grf`, `data.ini`, `System/` y el exe si cambió.

No hace falta re-descargar el cliente base salvo que cambies la fecha del cliente (`PACKETVER`); ver [client-packetver-warp.md](client-packetver-warp.md).

## `data.ini` (orden GRF)

```ini
[Data]
1=ozro.grf
2=renewal2021.grf
3=resources2021.grf
4=data.grf
5=rdata.grf
```

`ozro.grf` tiene prioridad 1: su contenido gana sobre los GRF de abajo.

---

## Reempaquetar cliente OzRo (desarrollador, Windows)

Las fuentes están en `ozro-cli/data/`. El GRF se arma con **GRF Editor** en Windows.

### 1. Generar itemInfo y preparar `dist/`

```bash
cd ozro-cli
npm run client:build
```

Esto genera `data/System/itemInfo_v5.lua` y `.lub`, y los copia a `dist/System/`.

### 1b. Si el cliente ya tiene `System/itemInfo.lua` o `itemInfo_EN.lua`

Muchos clientes traducidos (ROenglishRE) **leen `itemInfo_EN.lua`**, no `itemInfo.lua`. Si editas Zargon en `itemInfo.lua` y no cambia en el juego, el exe está usando el otro archivo.

En este repo el flujo es **generar desde base**, no parchear un cliente externo:

```bash
npm run client:generate-iteminfo
```

- Base: `data/System/itemInfo_EN.base.lua` (ROenglishRE sin custom items)
- Custom: `data/custom/items/itemInfo_custom.lua`
- Salida: `data/System/itemInfo_EN.lua` → incluido en `patch.zip`

**Prueba rápida:** cambia la descripción de Zargon (ID 912) en un archivo, reinicia el cliente y mira cuál se aplicó.

`data/luafiles514/` es para view IDs de accesorios (`accname.lub`, `AccessoryId.lub`), **no** para nombres/descripciones de ítems. Eso va en `System/itemInfo*.lua`.

Borra o renombra `System/itemInfo.lub` si solo contiene custom items (puede interferir).

### 2. Archivos a incluir en `ozro.grf`

En GRF Editor, añadir con estas rutas internas (barra invertida `\`):

| Archivo en disco | Ruta dentro del GRF |
|------------------|---------------------|
| `data/clientinfo.xml` | `data\clientinfo.xml` |
| `data/etcinfo.txt` | `data\etcinfo.txt` |
| `data/luafiles514/lua files/datainfo/tb_cashshop_banner.lub` | igual |
| `data/texture/scr_logo.bmp` | `data\texture\scr_logo.bmp` |
| `data/texture/.../loading00.jpg` … `loading06.jpg` | `data\texture\유저인터페이스\loadingXX.jpg` |
| `data/texture/.../cashshop/ozro00.bmp` etc. | `data\texture\유저인터페이스\cashshop\...` |
| `data/texture/.../t_배경*.bmp` | `data\texture\유저인터페이스\t_배경...` |
| `data/custom/items/texture/유저인터페이스/item/*.bmp` | `data\texture\유저인터페이스\item\ozro_*.bmp` |

**No incluir en el GRF:** `System/`, `data/custom/_ref/`, `data/custom/items/itemInfo_custom.lua`, `data/overrides/`.

### 3. Guardar y distribuir

1. Guardar como `release/ozro.grf`.
2. `npm run client:pack` → `dist/patch.zip` (exe, grf, data.ini, System/itemInfo_EN.lua).
3. Subir a la web / compartir con jugadores.

### Prueba rápida (sin repack GRF)

Para verificar que el itemInfo funciona:

1. `npm run client:build`
2. Copiar `dist/System/itemInfo_v5.lub` → `<cliente limpio>/System/itemInfo_v5.lub`
3. Reiniciar cliente, `@item Ozro_Bronze_Coin 1`

Si ahí funciona, el GRF estaba bien pero faltaba `System/` en disco.
