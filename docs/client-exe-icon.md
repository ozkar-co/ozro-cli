# Icono custom del exe (Resource Hacker)

Cosmético: no afecta al juego. Renombrar el exe basta; el icono es opcional.

## Archivo de icono

Usa el `.ico` ya generado en el repo:

```
ozro-cli/branding/OzRo.ico
```

(Multi-resolución: 256, 128, 64, 48, 32, 16 px, desde `ozro-site/public/favicon.png`.)

## Pasos en Windows

1. Descargar [Resource Hacker](http://www.angusj.com/resourcehacker/) si no lo tienes.
2. Abrir el exe parcheado (`OzRo.exe` o `Ragexe_patched.exe`).
3. Menú **Action** → **Replace Icon…**
4. Seleccionar el grupo de iconos (suele haber uno principal).
5. **Open file with new icon** → elegir `OzRo.ico`.
6. **Replace**.
7. **File** → **Save as** → `OzRo.exe`.

## Distribución

Incluir `OzRo.exe` (con icono) en el zip junto a `ozro.grf` y `data.ini`.
