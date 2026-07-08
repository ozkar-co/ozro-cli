# Cambiar PACKETVER y parchear el exe con WARP

Solo necesario cuando **actualizas rathena** y cambias la fecha del protocolo del cliente. No hace falta en cada cambio de `ozro.grf`.

## Cuándo hacerlo

- Subes rathena y cambias `PACKETVER` (hoy en `rathena/src/config/packets.hpp`: `20211103`).
- El exe del cliente debe corresponder a esa misma fecha.

## Advertencia RSU

**No uses RSU ai4rei** (`rsu-kro-*-lite.exe`) sobre un cliente que ya tiene `ozro.grf` u otros GRF custom mezclados: intenta parchear contra kRO oficial y puede **corromper `data.grf`**.

Si necesitas un cliente base más nuevo:
- RSU **oficial kRO** en Windows sobre un cliente **limpio**, o
- Pack comunitario renewal con la fecha deseada.

Luego vuelves a poner encima tu `ozro.grf` + `data.ini`.

---

## Paso 1 — Servidor (rathena)

Cambiar `PACKETVER` y recompilar:

**Linux (configure):**
```bash
cd rathena
./configure --enable-packetver=YYYYMMDD
make clean && make server
```

**O** crear `src/custom/defines_pre.hpp`:
```cpp
#define PACKETVER YYYYMMDD
```

La fecha `YYYYMMDD` debe coincidir con el `Ragexe.exe` que uses (ej. `20211103`).

---

## Paso 2 — Cliente base nuevo

Obtener un `Ragexe.exe` de esa fecha:
- Parchear cliente kRO limpio con RSU oficial (Windows), o
- Descargar pack comunitario renewal que ya incluya el exe.

---

## Paso 3 — WARP (exe para servidor privado)

El exe vanilla de Gravity no conecta a un servidor privado sin diffs.

1. Abrir **WARP** (WeeAvenger's Ragexe Patcher) en Windows.
2. Cargar el `Ragexe.exe` nuevo (sin parchear).
3. Aplicar parches habituales para private server (nombres pueden variar según versión WARP):
   - Desactivar GameGuard / nProtect
   - Permitir conexión a IP custom / quitar restricciones de login
   - Desactivar cifrado de paquetes si aplica
   - Permitir múltiples GRF (`data.ini`)
4. Guardar como `OzRo.exe` (o el nombre que distribuyas).

Si el juego crashea al iniciar, revisa que uses `Ragexe.exe` (renewal moderno), no `RagexeRE.exe`.

---

## Paso 4 — Overlay OzRo

1. Reempaquetar `ozro.grf` con GRF Editor (ver [client-install.md](client-install.md)).
2. Zip: `ozro.grf` + `data.ini` + `OzRo.exe`.
3. Opcional: icono con [client-exe-icon.md](client-exe-icon.md).

---

## Paso 5 — Verificar

1. `PACKETVER` en rathena = fecha del exe.
2. `data/clientinfo.xml` en `ozro.grf`: IP, puerto y `version` (55) aceptados por tu login.
3. Login al servidor.

Si falla el login, revisa packet version y que todos los GRF de `data.ini` existan en la carpeta del cliente.
