# OzRo Client

Configuración del cliente Ragnarok para OzRagnarok: `ozro.grf`, `data.ini`, y assets de UI.

## GRF tooling

Herramienta local en [`tools/grf/`](tools/grf/) para explorar GRFs y generar atlases WebP para la web.

```bash
# Instalar dependencias (una vez)
cd tools/grf && npm install

# Desde la raíz de ozro-cli:
npm run grf -- list --filter "texture/item" --limit 20
npm run grf -- info "data\\texture\\유저인터페이스\\item\\사과.bmp"
npm run grf -- extract "data\\sprite\\몬스터\\scorpion.spr" -o ./out

# Generar assets web → ozro-backup/assets/
npm run assets
```

Configuración en [`tools/grf/grf.config.json`](tools/grf/grf.config.json):
- `clientPath`: ruta al cliente RO completo (con `data.grf`, etc.)
- `outputPath`: destino de atlases (default: `ozro-backup/assets`)

## Custom GRF workflow

1. Editar archivos en `data/` (source of truth, versionado en git)
2. Items custom: ver [`data/custom/items/README.md`](data/custom/items/README.md)
3. Repack `ozro.grf` con **GRF Editor** (manual por ahora)
4. Desplegar `ozro.grf` + `data.ini` + exe en la carpeta del cliente

`data.ini` carga GRFs en orden de prioridad; `ozro.grf` (slot 1) gana sobre `data.grf`.

## Estructura

```
ozro-cli/
  data.ini
  ozro.grf
  data/              # Contenido del overlay GRF
  data/custom/       # Items y referencias custom
  tools/grf/         # CLI extracción + build assets
```
