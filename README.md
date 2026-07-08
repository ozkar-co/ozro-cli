# OzRo Client

Configuración del cliente Ragnarok para OzRagnarok: `ozro.grf`, `data.ini`, branding y custom items.

## Distribución (zip para jugadores)

```
ozro.grf
data.ini
OzRo.exe
```

Descomprimir sobre un cliente kRO completo. Ver [docs/client-install.md](docs/client-install.md).

## Workflow desarrollador

### 1. Editar fuentes en `data/`

- Branding: `data/clientinfo.xml`, `data/texture/`, `data/luafiles514/`
- Custom items: `data/custom/items/` (BMPs + `itemInfo_custom.lua`)

### 2. Generar itemInfo (opcional, antes de empaquetar)

```bash
npm run client:iteminfo
```

Escribe `data/System/itemInfo_v5.lua` (gitignored; incluir al empaquetar).

### 3. Reempaquetar `ozro.grf` — GRF Editor (Windows)

Ver [docs/client-install.md](docs/client-install.md) para la lista de archivos y rutas GRF.

### 4. Exe e icono (Windows)

- Parchear exe nuevo: [docs/client-packetver-warp.md](docs/client-packetver-warp.md) (WARP + PACKETVER)
- Icono: [docs/client-exe-icon.md](docs/client-exe-icon.md) + `branding/OzRo.ico`

### 5. Zip y publicar

`ozro.grf` + `data.ini` + `OzRo.exe` → web / Drive.

## GRF tooling (lectura + assets web)

Herramienta en [`tools/grf/`](tools/grf/) para explorar GRFs y generar atlases WebP.

```bash
cd tools/grf && npm install

npm run grf -- list --filter "texture/item" --limit 20
npm run assets   # atlases web → ozro-backup/assets/
```

## Estructura

```
ozro-cli/
  data.ini
  ozro.grf              # overlay GRF (reempaquetar en GRF Editor)
  branding/OzRo.ico     # icono para Resource Hacker
  data/                 # fuentes del overlay
  data/custom/items/    # custom items (monedas, apple)
  docs/                 # guías instalación, WARP, icono
  tools/grf/            # CLI lectura GRF + build assets web
  tools/client/         # npm run client:iteminfo
```

`data.ini` carga GRFs en orden; `ozro.grf` (slot 1) gana sobre `data.grf`.
