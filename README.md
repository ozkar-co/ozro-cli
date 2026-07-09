# OzRo Client

Parche del cliente Ragnarok Online para **OzRagnarok**: exe parcheado, GRFs de overlay, configuración de carga y traducción de items custom. Es un overlay sobre un cliente kRO completo (no incluye `data.grf` ni los GRF base).

Este repo guarda todo lo necesario para **distribuir el parche a jugadores** y para **reempaquetar el GRF** cuando haga falta cambiar branding, IP o assets.

## Estructura

### `patch/` — archivos para el zip

Archivos sueltos listos para **click derecho → Comprimir → enviar**.

```
OzRo.exe
ozro.grf
gefenia.grf
data.ini
System/itemInfo_EN.lua
OzRo.ico
```

### `dist/` — zip listo para compartir

El zip ya armado (`patch.zip`) para compartir link. Lo generas tu desde `patch/` y lo guardas aqui.

### `grf/` — fuentes del overlay GRF

Fuentes para reempaquetar `ozro.grf` en GRF Editor (Windows). Extraido de `patch/ozro.grf` (el que funciona).

```
grf/
  data/          ← arrastra esto al GRF Editor (rutas data\...)
    clientinfo.xml
    etcinfo.txt
    texture/
    luafiles514/
    custom/items/texture/   ← iconos custom van aqui DENTRO del GRF
  custom/        ← fuera de data: editas aqui, copias a data/custom/ antes de empaquetar
    items/
      itemInfo_custom.lua
      texture/유저인터페이스/item/*.bmp
```

Si cambias un icono: edita en `grf/custom/`, copia el BMP a `grf/data/custom/items/texture/유저인터페이스/item/`, empaqueta, copia el GRF a `patch/`.

**No meter en el GRF:** `itemInfo_custom.lua`, `System/` (va en `patch/`).

### Exe parcheado

`patch/OzRo.exe` es el Ragexe parcheado con WARP. No tocar salvo cambio de PACKETVER.
