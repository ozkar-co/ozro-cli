# OzRo Client

Tres carpetas. Nada de scripts.

## `parche/`

Archivos sueltos listos para **click derecho → Comprimir → enviar**.

```
OzRo.exe
ozro.grf
gefenia.grf
data.ini
System/itemInfo_EN.lua
OzRo.ico
INSTALL.txt
```

Cuando cambies algo, actualiza aqui y vuelve a zippear.

## `dist/`

El zip ya armado (`patch.zip`) para compartir link. Lo generas tu desde `parche/` y lo guardas aqui.

## `grf/`

Lo que metes en **GRF Editor** para crear `ozro.grf`. Luego copias el GRF a `parche/`.

| En disco (grf/) | Ruta dentro del GRF |
|-----------------|---------------------|
| `clientinfo.xml` | `data\clientinfo.xml` |
| `etcinfo.txt` | `data\etcinfo.txt` |
| `luafiles514/.../tb_cashshop_banner.lub` | igual |
| `texture/scr_logo.bmp` | `data\texture\scr_logo.bmp` |
| `texture/유저인터페이스/loading*.jpg` | `data\texture\유저인터페이스\loadingXX.jpg` |
| `texture/유저인터페이스/cashshop/*` | `data\texture\유저인터페이스\cashshop\...` |
| `texture/유저인터페이스/t_배경*.bmp` | `data\texture\유저인터페이스\t_배경...` |
| `custom/items/texture/유저인터페이스/item/*.bmp` | `data\texture\유저인터페이스\item\ozro_*.bmp` |

**No meter en el GRF:** `System/`, `custom/_ref/`, `itemInfo_custom.lua`.

Custom items: iconos BMP en `grf/custom/items/`, nombres en `parche/System/itemInfo_EN.lua`.

## Exe

`parche/OzRo.exe` es el Ragexe parcheado con WARP. No tocar salvo cambio de PACKETVER del servidor.
