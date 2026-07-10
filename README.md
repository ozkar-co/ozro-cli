# OzRo Client

Parche del cliente Ragnarok Online para **OzRagnarok**: exe parcheado, overlay en carpeta `data/`, configuración de carga y traducción de items custom. Es un overlay sobre un cliente kRO completo (no incluye `data.grf` ni los GRF base).

`OzRo.exe` lee primero la carpeta `data/` del disco, así que **no necesitamos GRF propio** (`ozro.grf`). Editamos archivos sueltos, los empaquetamos en el zip y listo.

## Estructura

### `patch/` — archivos para el zip

Archivos sueltos listos para **click derecho → Comprimir → enviar**.

```
OzRo.exe
data.ini
data/                    ← overlay custom (clientinfo, texturas, etc.)
System/itemInfo_EN.lua
```

`gefenia.grf` y `OzRo.ico` viven en `patch/` como referencia local pero no van en el zip de distribución.

### `dist/` — zip listo para compartir

El zip ya armado (`patch.zip`) para compartir link. Lo generas desde `patch/` y lo guardas aquí.

### `patch/data/` — overlay del cliente

Archivos que `OzRo.exe` carga directamente desde disco (prioridad sobre GRFs base).

```
data/
  clientinfo.xml         ← IP, puerto, loading screens (UTF-8)
  etcinfo.txt
  texture/
    유저인터페이스/      ← carpeta coreana (nombre exacto, no transliterar)
      loading*.jpg       ← pantallas de carga
      t_배경*.bmp        ← fondos del login (nombre coreano exacto)
      item/              ← iconos custom
  luafiles514/
```

### `custom/` — staging para ediciones

Editas aquí y copias a `patch/data/` antes de empaquetar.

```
custom/
  items/
    itemInfo_custom.lua          ← fuente de items custom (merge manual a patch/System/)
    texture/유저인터페이스/item/*.bmp
```

Si cambias un icono: edita en `custom/`, copia el BMP a `patch/data/texture/유저인터페이스/item/`, re-zip.

**No meter en `data/`:** `itemInfo_custom.lua`, `System/` (va suelto en `patch/`).

### Exe parcheado

`patch/OzRo.exe` es el Ragexe parcheado con WARP. No tocar salvo cambio de PACKETVER.

## Workflow

1. Editar assets en `patch/data/` (o staging en `custom/` → copiar)
2. Si hay items nuevos, actualizar `custom/items/itemInfo_custom.lua` y mergear en `patch/System/itemInfo_EN.lua`
3. Comprimir contenido de `patch/` (sin `gefenia.grf` ni `OzRo.ico`) → `dist/patch.zip`
4. Subir a Google Drive
