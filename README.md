# OzRo Client

Configuración del cliente Ragnarok para OzRagnarok: `ozro.grf`, `data.ini`, branding y custom items.

## Distribución (zip para jugadores)

```bash
npm run client:pack
```

Genera **`dist/patch.zip`** con `OzRo.exe`, `ozro.grf`, `data.ini` y `System/itemInfo_EN.lua`.  
Los jugadores extraen sobre su cliente kRO. Ver [docs/client-patch-zip.md](docs/client-patch-zip.md).

## Workflow desarrollador

### 1. Editar fuentes en `data/`

- Branding: `data/clientinfo.xml`, `data/texture/`, `data/luafiles514/`
- Custom items: `data/custom/items/` (BMPs + `itemInfo_custom.lua`)

### 2. Custom items en el cliente (ROenglishRE)

El `itemInfo` base vive en el repo — no hace falta copiar desde un cliente instalado:

```
data/System/itemInfo_EN.base.lua   ← ROenglishRE sin custom items (commit)
data/custom/items/itemInfo_custom.lua
        ↓ npm run client:generate-iteminfo
data/System/itemInfo_EN.lua        ← generado (gitignored)
```

```bash
npm run client:generate-iteminfo
```

`client:pack` regenera `itemInfo_EN.lua` automáticamente antes de armar el zip.

Importar base desde un cliente ya parcheado (solo una vez):

```bash
npm run client:import-base -- "C:/ruta/cliente/System/itemInfo_EN.lua"
```

### 3. Reempaquetar `ozro.grf` — GRF Editor (Windows)

Ver [docs/client-install.md](docs/client-install.md) para la lista de archivos y rutas GRF.  
Copia el GRF resultante a `release/ozro.grf`.

### 4. Exe (WARP)

Ver [docs/client-packetver-warp.md](docs/client-packetver-warp.md) y [docs/client-exe-icon.md](docs/client-exe-icon.md).  
Copia el exe parcheado a `release/ozro_patched.exe`.

### 5. Armar y publicar `patch.zip`

```bash
cp pack.config.example.json pack.config.json   # una vez
npm run client:pack
```

Sube `dist/patch.zip` a web / Drive.

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
  pack.config.json      # rutas locales (gitignored; ver pack.config.example.json)
  data.ini
  data/System/
    itemInfo_EN.base.lua  # base ROenglishRE (commit)
    itemInfo_EN.lua       # generado (gitignored)
  data/                 # fuentes del overlay GRF
  release/              # ozro.grf + ozro_patched.exe
  dist/patch.zip        # generado por npm run client:pack (gitignored)
  docs/
  tools/client/         # generate-iteminfo, pack
  tools/grf/
```

`data.ini` carga GRFs en orden; `ozro.grf` (slot 1) gana sobre `data.grf`.
