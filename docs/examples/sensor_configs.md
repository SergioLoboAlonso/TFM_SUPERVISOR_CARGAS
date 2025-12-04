# Ejemplos de Configuración de Sensores

Este documento muestra diferentes perfiles de configuración para nodos con distintos tipos de sensores, editando únicamente `platformio.ini`.

## Perfil 1: Inclinómetro (producción, default)

**Uso:** Nodo con solo MPU6050 para medición de ángulos y vibración.

```ini
[env:uno]
build_flags =
  # ... otros flags ...
  -DSENSORS_MPU_ENABLED=1
  -DSENSORS_TEMP_ENABLED=0
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_USE_MOCK=0
```

**Resultado:**
- Solo se compila `MPU6050Sensor`
- `sensor_mpu0` registrado en `setup()`
- RAM: ~816 bytes, Flash: ~13.3 KB

**Compilar y flashear:**
```bash
pio run -e uno -t upload
```

---

## Perfil 2: Temperatura standalone (producción)

**Uso:** Nodo con sensor de temperatura DS18B20 o DHT22 (cuando esté implementado).

```ini
[env:uno]
build_flags =
  # ... otros flags ...
  -DSENSORS_MPU_ENABLED=0
  -DSENSORS_TEMP_ENABLED=1
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_USE_MOCK=0          # Cambiar a 1 si no hay HW
```

**Resultado:**
- Solo `TemperatureSensor` compilado
- Si `MOCK=0` y HW no implementado: sensor no estará disponible pero firmware arranca
- Si `MOCK=1`: genera datos sintéticos 20-25°C

---

## Perfil 3: Multi-sensor (demo MOCK)

**Uso:** Desarrollo sin hardware, simular nodo con múltiples sensores.

```ini
[env:uno]
build_flags =
  # ... otros flags ...
  -DSENSORS_MPU_ENABLED=1
  -DSENSORS_TEMP_ENABLED=1
  -DSENSORS_ACCEL_ENABLED=1
  -DSENSORS_LOAD_ENABLED=1
  -DSENSORS_USE_MOCK=1          # ← Clave: todos generan datos sintéticos
```

**Resultado:**
- 4 sensores compilados: `sensor_mpu0`, `sensor_temp0`, `sensor_accel0`, `sensor_load0`
- Todos `begin()` exitosos (modo MOCK siempre devuelve `true`)
- Telemetría variada: ángulos, accel, gyro, temperaturas mezcladas
- Útil para probar Edge Python sin conectar sensores

**Validar salida:**
```bash
pio device monitor
# Observar registros Modbus actualizándose periódicamente
```

---

## Perfil 4: Inclinómetro + Temperatura (producción)

**Uso:** Nodo que mide inclinación y temperatura ambiente (aplicación típica).

```ini
[env:uno]
build_flags =
  # ... otros flags ...
  -DSENSORS_MPU_ENABLED=1
  -DSENSORS_TEMP_ENABLED=1
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_USE_MOCK=0
```

**Resultado:**
- `MPU6050Sensor` aporta: ángulos, accel, gyro, temp interna MPU
- `TemperatureSensor` aporta: temp externa (DS18B20 preferido para mayor precisión)
- Dos fuentes de temperatura; última escritura gana (orden de registro importa)

**Orden de registro en `main.cpp`:**
```cpp
sensorManager.registerSensor(&sensor_mpu0);    // Primero MPU
sensorManager.registerSensor(&sensor_temp0);   // Luego temp → sobreescribe temp en Modbus
```

---

## Perfil 5: Solo carga/corriente (producción futura)

**Uso:** Nodo dedicado a medir carga eléctrica o peso con celda de carga.

```ini
[env:uno]
build_flags =
  # ... otros flags ...
  -DSENSORS_MPU_ENABLED=0
  -DSENSORS_TEMP_ENABLED=0
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=1
  -DSENSORS_USE_MOCK=0
```

**Pendiente:**
- Implementar driver HX711 (celda carga) o ACS712 (corriente) en `LoadSensor::begin()` y `poll()`
- Mapear salida a campo de `TelemetryDelta` apropiado (podría reutilizar `temp_mc` o añadir campo dedicado)

---

## Cambiar entre perfiles sin editar código

1. Editar solo `platformio.ini` → sección `[env:uno]` → `build_flags` → cambiar `-DSENSORS_*_ENABLED`
2. Ejecutar `pio run -e uno`
3. Firmware se recompila con nueva configuración
4. Flashear con `pio run -e uno -t upload`

**No se requiere tocar:**
- `main.cpp`
- Ningún archivo en `firmware/lib/Sensors/`
- Código de drivers

---

## Verificar configuración activa

En tiempo de compilación, PlatformIO mostrará qué librerías se incluyen:

```
Scanning dependencies...
Dependency Graph
|-- Wire @ 1.0
|-- Sensors
|-- MPU6050Driver         ← Solo si SENSORS_MPU_ENABLED=1
|-- AngleCalculator       ← Solo si SENSORS_MPU_ENABLED=1
|-- BlinkIdent
|-- ModbusRTU
```

Si `SENSORS_MPU_ENABLED=0`, `MPU6050Driver` no aparecerá en el árbol.

---

## Buenas prácticas

- **Producción:** `SENSORS_USE_MOCK=0` siempre
- **Desarrollo sin HW:** `SENSORS_USE_MOCK=1` + habilitar sensores deseados
- **Nodo específico:** Habilitar solo sensores necesarios → ahorra RAM/Flash
- **Multi-sensor:** Máximo 4 sensores por defecto (`MAX_SENSORS`); editar `SensorManager.h` si necesitas más

---

## RAM/Flash estimados por sensor

| Sensor            | Flash (bytes) | RAM (bytes) | Notas                          |
|-------------------|---------------|-------------|--------------------------------|
| MPU6050Sensor     | ~8 KB         | ~150        | Incluye driver + angles        |
| TemperatureSensor | ~500          | ~20         | Stub actual; real depende de HW|
| AccelerometerSensor| ~500         | ~20         | Stub actual                    |
| LoadSensor        | ~500          | ~20         | Stub actual                    |
| SensorManager     | ~1 KB         | ~50         | Base + applyTelemetry          |

**Total con 1 sensor MPU:** ~13.3 KB Flash, ~816 bytes RAM (incluye Modbus, BlinkIdent, etc.)

---

## Preguntas frecuentes

**Q: ¿Puedo tener dos instancias del mismo sensor (p.ej., 2 MPU6050 en diferentes direcciones I²C)?**  
A: Sí, declarar dos instancias con direcciones distintas:
```cpp
static MPU6050Sensor sensor_mpu0(0x68);
static MPU6050Sensor sensor_mpu1(0x69);
sensorManager.registerSensor(&sensor_mpu0);
sensorManager.registerSensor(&sensor_mpu1);
```
Compilar con `-DSENSORS_MPU_COUNT=2` (opcional, informativo).

**Q: ¿Cómo añado un nuevo tipo de sensor no listado?**  
A: Ver `firmware/lib/Sensors/README.md` → sección "Añadir un nuevo tipo de sensor".

**Q: ¿El modo MOCK afecta rendimiento?**  
A: No. Las sentencias `#if SENSORS_USE_MOCK` se evalúan en compilación; código no usado no se incluye en el binario.

**Q: ¿Puedo cambiar intervalo de muestreo por sensor?**  
A: Sí, pasar parámetro al constructor:
```cpp
static MPU6050Sensor sensor_mpu0(0x68, 50);  // 50 ms → 20 Hz
static TemperatureSensor sensor_temp0(1000); // 1000 ms → 1 Hz
```
