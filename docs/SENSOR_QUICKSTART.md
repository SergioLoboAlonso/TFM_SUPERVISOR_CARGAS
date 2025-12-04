# Quick Start: Configurar Sensores en 3 Pasos

Esta guía te permite configurar sensores en tu nodo sin tocar código C++.

---

## Paso 1: Editar `platformio.ini`

Abre `platformio.ini` (raíz del proyecto) y localiza la sección `[env:uno]` (o `[env:nano]`).

Busca las líneas con `SENSORS_*`:

```ini
build_flags =
  # ... otros flags ...
  -DSENSORS_MPU_ENABLED=1        # ← Cambiar a 0 para deshabilitar MPU6050
  -DSENSORS_TEMP_ENABLED=0       # ← Cambiar a 1 para habilitar temperatura
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_USE_MOCK=0           # ← Cambiar a 1 para datos sintéticos (sin HW)
```

**Valores:**
- `=1` → Sensor **habilitado** (se compila e instancia)
- `=0` → Sensor **deshabilitado** (no consume RAM/Flash)

**Ejemplo:** Nodo con MPU6050 y sensor de temperatura:
```ini
  -DSENSORS_MPU_ENABLED=1
  -DSENSORS_TEMP_ENABLED=1
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_USE_MOCK=0
```

---

## Paso 2: Compilar

Guarda `platformio.ini` y ejecuta:

```bash
pio run -e uno
```

**Verifica la salida:**
```
Dependency Graph
|-- Sensors
|-- MPU6050Driver         ← Aparece solo si SENSORS_MPU_ENABLED=1
|-- Wire
|-- ModbusRTU
...
✓ RAM: ~800 bytes
✓ Flash: ~13 KB
```

Si ves errores, revisa que las macros `SENSORS_*` tengan formato correcto (`-DNOMBRE=valor`, sin espacios).

---

## Paso 3: Flashear

Conecta el Arduino y ejecuta:

```bash
pio run -e uno -t upload
```

**Monitor serial:**
```bash
pio device monitor
```

Si `SENSORS_USE_MOCK=1`, verás datos sintéticos actualizándose.

---

## 🎯 Casos de uso rápidos

### Solo inclinómetro (MPU6050)
```ini
-DSENSORS_MPU_ENABLED=1
-DSENSORS_TEMP_ENABLED=0
-DSENSORS_ACCEL_ENABLED=0
-DSENSORS_LOAD_ENABLED=0
-DSENSORS_USE_MOCK=0
```
↳ Mide ángulos pitch/roll, aceleración, giro, temperatura interna.

### Demo sin hardware (todos los sensores MOCK)
```ini
-DSENSORS_MPU_ENABLED=1
-DSENSORS_TEMP_ENABLED=1
-DSENSORS_ACCEL_ENABLED=1
-DSENSORS_LOAD_ENABLED=1
-DSENSORS_USE_MOCK=1
```
↳ Genera datos sintéticos; útil para probar Edge/MQTT sin sensores físicos.

### Temperatura standalone
```ini
-DSENSORS_MPU_ENABLED=0
-DSENSORS_TEMP_ENABLED=1
-DSENSORS_ACCEL_ENABLED=0
-DSENSORS_LOAD_ENABLED=0
-DSENSORS_USE_MOCK=0   # Cambiar a 1 si no tienes sensor DS18B20/DHT22
```
↳ Solo mide temperatura; ahorra RAM/Flash.

---

## 🔧 Solución de problemas

**Error: `SENSORS_MPU_ENABLED undeclared`**
→ Asegúrate de que el flag esté en `build_flags` de `platformio.ini` **antes** de `-Ifirmware/include`.

**El sensor no funciona (HW conectado pero sin datos)**
→ Verifica:
1. `SENSORS_USE_MOCK=0` (modo producción)
2. Conexiones I²C correctas (A4/A5 en UNO)
3. `begin()` del sensor devuelve `true` (añadir logs en `SensorManager::beginAll()`)

**Quiero más de 4 sensores**
→ Edita `firmware/lib/Sensors/include/SensorManager.h`:
```cpp
static const uint8_t MAX_SENSORS = 8;  // Era 4
```
Recompila.

**¿Cómo sé qué sensores están activos?**
→ Mira la salida de compilación (`Dependency Graph`). Solo aparecen librerías de sensores habilitados.

---

## 📚 Más información

- **Arquitectura completa:** `docs/SENSOR_IMPLEMENTATION.md`
- **Ejemplos de configuración:** `docs/examples/sensor_configs.md`
- **API de sensores:** `firmware/lib/Sensors/README.md`
- **Añadir nuevo sensor:** `firmware/lib/Sensors/README.md` → sección "Añadir un nuevo tipo de sensor"

---

## ✅ Checklist

- [ ] Editar `platformio.ini` → `build_flags` → `SENSORS_*_ENABLED`
- [ ] Ejecutar `pio run -e uno` → verificar compilación OK
- [ ] Flashear con `pio run -e uno -t upload`
- [ ] Monitor serial: `pio device monitor` → validar telemetría

¡Listo! Tu nodo está configurado con los sensores deseados.
