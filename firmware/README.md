# Firmware

Código para microcontroladores AVR (Arduino UNO/NANO) que implementa un esclavo Modbus RTU sobre RS‑485 con captura de datos de sensores y utilidades de dispositivo (identificación LED, EEPROM, estado).

## Estructura
- `platformio.ini` (en repo raíz): configuración de entornos (UNO, NANO), flags y pines, **habilitación de sensores**.
- `src/` → Punto de entrada (`main.cpp`): Modbus + BlinkIdent + orquestación de sensores vía `SensorManager` (sin lógica inline).
- `include/` → Cabeceras globales de firmware: pines (`config_pins.h`), versión (`firmware_version.h`).
- `lib/` → Librerías locales:
	- **`Sensors/`** → **Arquitectura normalizada de sensores** (ISensor, SensorManager, TelemetryDelta, configuración por compilación). Ver `lib/Sensors/README.md`.
	- `ModbusRTU/` → Servidor RTU y mapa de registros. Ver `lib/ModbusRTU/README.md`.
	- `MPU6050Driver/` → Driver I²C para MPU-6050 (acelerómetro/giroscopio/temp).
	- `AngleCalculator/` → Cálculo de ángulos pitch/roll desde acelerómetro.
	- `BlinkIdent/` → Patrones no bloqueantes de identificación LED.
	- `EepromUtils/` → Persistencia de UnitID/alias.
	- `StateMachine/` → Orquestación (descubrimiento/claim/operar) — placeholder.
	- `utils/` → CRC16 Modbus y utilidades.
- `test/` → Pruebas Unity (PlatformIO): CRC16, mapa de registros, sensores MPU6050.

## Componentes clave

### Sensors (arquitectura nueva)
**Abstracción modular sin lógica en `main.cpp`.**

- **`ISensor.h`** — Interfaz base para todos los sensores (`begin()`, `poll()`, `isAvailable()`).
- **`SensorTypes.h`** — `TelemetryDelta` (unidades normalizadas: mg, mdps, mdeg, mc) y `SensorKind` (enumeración de tipos).
- **`SensorConfig.h`** — Configuración por compilación: `SENSORS_MPU_ENABLED`, `SENSORS_TEMP_ENABLED`, etc. (editar en `platformio.ini`).
- **`SensorManager.h/.cpp`** — Orquestador central: registra sensores, llama `poll()` periódicamente, vuelca `TelemetryDelta` a registros Modbus vía `regs_set_*`.

**Sensores disponibles:**
1. **MPU6050Sensor** (producción) — IMU completo (ángulos, accel, gyro, temp).
2. **TemperatureSensor** (stub) — Sensor genérico de temperatura (con modo MOCK).
3. **AccelerometerSensor** (stub) — Acelerómetro dedicado (con modo MOCK).
4. **LoadSensor** (stub) — Carga/corriente (con modo MOCK).

**Configuración (en `platformio.ini`):**
```ini
build_flags =
  -DSENSORS_MPU_ENABLED=1        # Habilitar MPU6050
  -DSENSORS_TEMP_ENABLED=0       # Deshabilitar temperatura
  -DSENSORS_ACCEL_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_USE_MOCK=0           # 0=HW real, 1=datos sintéticos
```

Solo se compilan e instancian los sensores habilitados → ahorra RAM/Flash.

**Ver documentación completa:**
- **Quick Start:** `docs/SENSOR_QUICKSTART.md` — Configurar sensores en 3 pasos.
- **Ejemplos de configuración:** `docs/examples/sensor_configs.md` — Perfiles de nodos (inclinómetro, multi-sensor, etc.).
- **API y arquitectura:** `firmware/lib/Sensors/README.md` — Añadir nuevos sensores, flujo de datos.
- **Implementación detallada:** `docs/SENSOR_IMPLEMENTATION.md` — Resumen técnico completo.

### ModbusRTU + registersModbus
- Archivo de cabecera canónica: `lib/ModbusRTU/include/registersModbus.h`.
- Reglas y contrato del mapa:
	- Direcciones base‑0. Holding 0x0000..0x002F; Input 0x0000..0x001F.
	- Lectura máx. por trama: 32 palabras (ver `MAX_*_READ`).
	- Escalas: ángulos 0.01°, temp 0.01°C, acel. mg, giro mdps.
	- Broadcast (unit=0): sólo 0x06 y sin respuesta.
- API de acceso en tiempo de ejecución: `regs_*` para leer/escribir y actualizar estado.
- Excepciones manejadas: función/valor/dirección ilegal.

Consulta el documento: `lib/ModbusRTU/README.md` (tabla completa del mapa y notas RTU).

### MPU6050Driver + AngleCalculator
- **MPU6050Driver:** Comunicación I²C con MPU-6050, lectura escalada (mg, mdps, centésimas °C), configuración de rangos y filtros DLPF.
- **AngleCalculator:** Cálculo de ángulos pitch/roll desde acelerómetro con filtro EMA opcional; salida en mdeg.
- Usados internamente por `MPU6050Sensor`; no requieren integración manual en `main.cpp`.

### BlinkIdent
Patrones de parpadeo no bloqueantes para la función "Identify" (controlada por `HR_CMD_IDENT_SEGUNDOS`). Se actualiza en cada `loop()` sin `delay()`.

### EepromUtils
Persistencia de UnitID y otros metadatos. Proporciona helpers para leer/escribir de forma segura.

## Compilación y carga

- Requisitos: PlatformIO Core/VS Code + toolchain AVR.
- UNO por defecto. Para compilar y subir:
```bash
pio run -e uno -t upload
```

**Cambiar configuración de sensores:**
Edita `platformio.ini` → `build_flags` → `SENSORS_*_ENABLED` → recompila. No se requiere tocar código C++.

## Pruebas unitarias

- Ubicadas en `firmware/test/` con Unity.
- Incluyen:
	- `test_crc16.cpp`: vectores conocidos y caso vacío.
	- `test_modbus_map.cpp`: límites de ventana, escrituras válidas/ilegales, diagnósticos.
	- `test_mpu6050.cpp`: driver MPU6050, cálculo de ángulos, filtros.
- Se ejecutan sobre la placa (HIL) usando PlatformIO Test Runner:
```bash
pio test -e uno
```

## Convenciones

- Nombres de registros en castellano y autoexplicativos (p.ej., `HR_INFO_VERSION_FW`).
- Mantener estabilidad de direcciones; añadir nuevos al final del banco correspondiente.
- Big‑endian en el cable; internos como `uint16_t`.
- **Sensores:** nombres de instancias descriptivos (`sensor_mpu0`, `sensor_temp0`), variables legibles (`sensor_count_`).
- **Unidades normalizadas:** mg (accel), mdps (gyro), mdeg (ángulos), mc (temp).

## Flujo de datos

```
Sensor HW → Sensor::poll() → TelemetryDelta → SensorManager::applyTelemetry()
→ regs_set_*() → Registros Modbus → RS-485 → Edge Python → MQTT → FIWARE
```

## Próximos pasos

- [ ] Implementar drivers reales para TemperatureSensor (DS18B20/DHT22), LoadSensor (HX711/ACS712).
- [ ] Validar MPU6050 en hardware real.
- [ ] Añadir calibración automática de offsets en MPU6050.
- [ ] Implementar `StateMachine` (discovery/claim/operate).
- [ ] Mapear registros de configuración Modbus a parámetros de sensores (DLPF, rangos).
- [ ] Añadir pruebas para 0x06 broadcast y contadores de diagnóstico bajo carga.

