# Icono custom del exe

Cosmético: no afecta al juego. Renombrar el exe basta; el icono es opcional.

## Archivo de icono

Usa el `.ico` ya generado en el repo:

```
ozro-cli/branding/OzRo.ico
```

(Multi-resolución: 256, 128, 64, 48, 32, 16 px, desde `ozro-site/public/favicon.png`.)

## Método recomendado: WARP

Como el exe ya se parchea con **WARP** para el servidor privado, aprovecha su reemplazo de icono
en el mismo paso (evita abrir un segundo programa):

1. En WARP, cargar el `Ragexe.exe`.
2. Buscar el parche de icono (suele llamarse "Replace Icon" / "Custom Icon").
3. Seleccionar `branding/OzRo.ico`.
4. Aplicar el resto de parches y guardar como `OzRo.exe`.

> Nota: editar el icono con **Resource Hacker** sobre un exe ya parcheado puede **romperlo**
> (pasó en OzRo). Si usas Resource Hacker, hazlo sobre el exe vanilla ANTES de parchear con WARP,
> o simplemente usa el reemplazo de icono de WARP.

## Alternativa: Resource Hacker (si WARP no trae icono)

1. Descargar [Resource Hacker](http://www.angusj.com/resourcehacker/).
2. Abrir el exe.
3. **Action** → **Replace Icon…**
4. Seleccionar el grupo de iconos principal.
5. **Open file with new icon** → `OzRo.ico` → **Replace**.
6. **File** → **Save as** → `OzRo.exe`.

Si el exe deja de arrancar tras esto, vuelve al método WARP.

## Distribución

Incluir `OzRo.exe` (con icono) en el zip junto a `ozro.grf` y `data.ini`.
