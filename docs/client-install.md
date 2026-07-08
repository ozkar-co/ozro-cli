# Instalación del cliente OzRo

El zip OzRo es un **overlay** sobre un cliente kRO completo. No incluye `data.grf` ni los GRF base (~4 GB).

## Contenido del zip OzRo

```
ozro.grf          # overlay (branding, IP, custom items)
data.ini          # orden de carga GRF
OzRo.exe          # exe parcheado para servidor privado
```

## Primera instalación (jugador)

1. Descargar el **cliente kRO completo** (Google Drive / pack comunitario).
   Debe incluir al menos: `data.grf`, `renewal2021.grf`, `resources2021.grf`, `rdata.grf`.
2. Descomprimir el **zip OzRo** encima de la carpeta del cliente (sobrescribe/añade archivos).
3. Ejecutar `OzRo.exe` desde esa carpeta.

## Actualización OzRo (mismo cliente base)

1. Descomprimir el zip nuevo **sobre la carpeta existente**.
2. Sobrescribe `ozro.grf`, `data.ini` y el exe si cambió.

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

## Reempaquetar `ozro.grf` (desarrollador, Windows)

Las fuentes están en `ozro-cli/data/`. El GRF se arma con **GRF Editor** en Windows.

### 1. Generar itemInfo (Linux o Windows)

```bash
cd ozro-cli
npm run client:iteminfo
```

Crea `data/System/itemInfo_v5.lua` a partir de `data/custom/items/itemInfo_custom.lua`.

### 2. Archivos a incluir en `ozro.grf`

En GRF Editor, añadir con estas rutas internas (barra invertida `\`):

| Archivo en disco | Ruta dentro del GRF |
|------------------|---------------------|
| `data/clientinfo.xml` | `data\clientinfo.xml` |
| `data/etcinfo.txt` | `data\etcinfo.txt` |
| `data/System/itemInfo_v5.lua` | `data\System\itemInfo_v5.lua` |
| `data/luafiles514/lua files/datainfo/tb_cashshop_banner.lub` | igual |
| `data/texture/scr_logo.bmp` | `data\texture\scr_logo.bmp` |
| `data/texture/.../loading00.jpg` … `loading06.jpg` | `data\texture\유저인터페이스\loadingXX.jpg` |
| `data/texture/.../cashshop/ozro00.bmp` etc. | `data\texture\유저인터페이스\cashshop\...` |
| `data/texture/.../t_배경*.bmp` | `data\texture\유저인터페이스\t_배경...` |
| `data/custom/items/texture/유저인터페이스/item/*.bmp` | `data\texture\유저인터페이스\item\ozro_*.bmp` |

La carpeta de textura en disco puede verse como `À¯ÀúÀÎÅÍÆäÀÌ½º` (mojibake); dentro del GRF debe ser `유저인터페이스`.

**No incluir:** `data/custom/_ref/`, `data/custom/items/itemInfo_custom.lua`, `data/overrides/`.

### 3. Guardar y distribuir

1. Guardar como `ozro.grf` en la raíz de `ozro-cli` (o copiar al zip).
2. Zip: `ozro.grf` + `data.ini` + `OzRo.exe`.
3. Subir a la web / compartir con jugadores.
