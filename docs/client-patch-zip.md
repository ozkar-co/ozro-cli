# Distribución del parche OzRo (`patch.zip`)

Zip para jugadores: extraer sobre la carpeta del cliente kRO (donde está `data.grf`).

## Contenido de `patch.zip`

```
OzRo.exe
ozro.grf
data.ini
System/
  itemInfo_EN.lua
INSTALL.txt
```

## Workflow desarrollador

### 1. Configurar rutas (una vez)

```bash
cp pack.config.example.json pack.config.json
```

Por defecto apunta a `release/ozro_patched.exe` y `release/ozro.grf`. No hace falta `clientPath`.

### 2. Tras cambiar custom items

Edita `data/custom/items/itemInfo_custom.lua`, luego:

```bash
npm run client:generate-iteminfo
```

El script combina:

- `data/System/itemInfo_EN.base.lua` — base ROenglishRE (commit en git)
- `data/custom/items/itemInfo_custom.lua` — IDs OzRo (35001+)

Salida: `data/System/itemInfo_EN.lua` (gitignored; `client:pack` lo regenera igual).

### 3. Tras cambiar GRF o exe

- Reempaqueta `ozro.grf` en GRF Editor (fuentes en `data/`) → copia a `release/ozro.grf`
- Parchea exe con WARP si cambió PACKETVER → copia a `release/ozro_patched.exe`

### 4. Armar zip para jugadores

```bash
npm run client:pack
```

Salida: **`dist/patch.zip`** — enviar a jugadores.

Toma binarios desde `release/` y `itemInfo_EN.lua` generado desde el base del repo.

### 5. Instalación jugador

1. Cerrar el juego
2. Extraer `patch.zip` sobre la carpeta del cliente
3. Reemplazar archivos
4. Abrir `OzRo.exe`

No hace falta re-descargar el cliente base salvo cambio de `PACKETVER`.

### Importar base (solo una vez)

Si actualizas ROenglishRE en un cliente y quieres refrescar el base del repo:

```bash
npm run client:import-base -- "C:/ruta/cliente/System/itemInfo_EN.lua"
```

Esto escribe `data/System/itemInfo_EN.base.lua` (sin IDs 35001+). Haz commit de ese archivo.
