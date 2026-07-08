# OzRo custom items — plantilla inicial

IDs reservados en `rathena/db/import/item_db.yml` (rango 35000–35099).

| ID | AegisName | Base vanilla | Uso |
|----|-----------|--------------|-----|
| 35001 | Ozro_Platinum_Coin | Platinum Coin (677) | Moneda premium NPC |
| 35002 | Ozro_Gold_Coin | Gold Coin (671) | Moneda alta |
| 35003 | Ozro_Silver_Coin | Silver Coin (675) | Moneda media |
| 35004 | Ozro_Bronze_Coin | Bronze Coin (673) | Moneda baja |
| 35010 | Ozro_Apple | Apple (512) | Consumible test scripts |

## Estructura GRF-ready

```
data/
  custom/
    _ref/icons/          # Referencias extraídas del GRF (no empaquetar)
    items/
      texture/유저인터페이스/item/
        ozro_platinum_coin.bmp
        ozro_gold_coin.bmp
        ...
      itemInfo_custom.lua  # Entradas para fusionar en System/itemInfo.lua
```

## Workflow

1. **Extraer referencias** (ya hecho en `_ref/icons/`):
   ```bash
   cd ozro-cli/tools/grf
   npm run grf -- info "data\\texture\\유저인터페이스\\item\\금화.bmp"
   ```

2. **Editar iconos** en `data/custom/items/texture/유저인터페이스/item/` (24×24 BMP indexado).

3. **Añadir entradas** en `itemInfo_custom.lua` con el `identifiedResourceName` que coincida con el nombre del BMP (sin extensión).

4. **Server-side**: definir items en `rathena/db/import/item_db.yml` con los IDs de arriba.

5. **Repack `ozro.grf`** con GRF Editor (Windows):
   - `npm run client:iteminfo` (genera `data/System/itemInfo_v5.lua`)
   - Añadir archivos según [docs/client-install.md](../../docs/client-install.md)
   - `ozro.grf` tiene prioridad 1 en `data.ini`

6. **Regenerar assets web** (opcional):
   ```bash
   cd ozro-cli && npm run assets
   ```

## Resource names (cliente)

| Item | ResourceName BMP |
|------|------------------|
| Ozro Platinum Coin | `ozro_platinum_coin` |
| Ozro Gold Coin | `ozro_gold_coin` |
| Ozro Silver Coin | `ozro_silver_coin` |
| Ozro Bronze Coin | `ozro_bronze_coin` |
| Ozro Apple | `ozro_apple` |

Los BMP iniciales son copias de las monedas/apple vanilla — edítalos para personalizar.
