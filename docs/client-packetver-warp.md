# Alinear PACKETVER y parchear el exe con WARP

Solo necesario cuando **actualizas rathena** y cambias la fecha del protocolo del cliente. No hace falta en cada cambio de `ozro.grf`.

## Qué es (y qué NO es) el PACKETVER

- El **PACKETVER es la fecha del `Ragexe.exe`** que descargas. Un exe del 2021-11-03 "habla" 20211103; eso viene fijo en ese binario.
- **WARP no cambia el PACKETVER.** WARP (y Nemo) solo aplican *diffs de comportamiento* al exe (desactivar GameGuard, permitir tu servidor, icono, título, etc.).
- Para "alinear" el PACKETVER se hacen dos cosas independientes:
  1. **Servidor**: poner el mismo número en rathena (`#define`/configure).
  2. **Cliente**: descargar el `Ragexe.exe` de esa fecha.

En resumen: no se "setea" una fecha en el exe; se **elige el exe correcto** y se le hace match en el servidor.

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

## Paso 2 — Cliente base con el exe de esa fecha

El PACKETVER lo trae el exe, así que consíguelo ya con la fecha correcta:
- Parchear cliente kRO limpio con RSU oficial (Windows), o
- Descargar pack comunitario renewal que ya incluya el `Ragexe.exe` de esa fecha.

No hay forma de "cambiar la fecha" de un exe existente; se reemplaza por el de la fecha deseada.

---

## Paso 3 — WARP (parchear el exe para servidor privado)

El exe vanilla de Gravity no conecta a un servidor privado sin diffs.

1. Abrir **WARP** (WeeAvenger's Ragexe Patcher) en Windows.
2. Cargar el `Ragexe.exe` nuevo (sin parchear).
3. Aplicar parches habituales para private server (nombres varían según versión WARP):
   - Desactivar GameGuard / nProtect
   - Permitir conexión a tu servidor / quitar restricciones de login
   - Desactivar cifrado de paquetes si aplica
   - Permitir múltiples GRF (`data.ini`)
   - (Opcional) Reemplazar icono y título de ventana — ver [client-exe-icon.md](client-exe-icon.md)
4. Guardar como `OzRo.exe` (o el nombre que distribuyas).

Si el juego crashea al iniciar, revisa que uses `Ragexe.exe` (renewal moderno), no `RagexeRE.exe`.

---

## Paso 4 — Overlay OzRo

1. Reempaquetar `ozro.grf` con GRF Editor (ver [client-install.md](client-install.md)).
2. Zip: `ozro.grf` + `data.ini` + `OzRo.exe`.

---

## Paso 5 — Verificar

1. `PACKETVER` en rathena = fecha del exe.
2. `data/clientinfo.xml` en `ozro.grf`: IP, puerto y `version` (55) aceptados por tu login.
3. Login al servidor.

Si falla el login, revisa packet version y que todos los GRF de `data.ini` existan en la carpeta del cliente.
