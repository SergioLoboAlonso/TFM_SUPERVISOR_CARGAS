# Sensors module

Abstracción y orquestación de sensores para el firmware. Evita lógica en `main.cpp` y normaliza la telemetría a las unidades del contrato Modbus.

## Componentes

- `ISensor.h` — Interfaz base de sensores (begin, poll, isAvailable).
- `SensorTypes.h` — Tipos normalizados de telemetría (mg, mdps, mdeg, mc) y enumeración de sensores.
- `SensorConfig.h` — Configuración por compilación (habilitación de sensores, cuentas, modo MOCK).
- `SensorManager.h/.cpp` — Orquestador que registra, inicializa, hace poll no bloqueante y vuelca a registros Modbus vía `regs_set_*`.

### Sensores disponibles

1. **MPU6050Sensor** (`MPU6050Sensor.h`) — IMU para inclinometría (ángulos pitch/roll), acelerómetro, giroscopio y temperatura.
2. **TemperatureSensor** (`TemperatureSensor.h`) — Sensor de temperatura (DS18B20 con OneWire/Dallas o MOCK).
3. **AccelerometerSensor** (`AccelerometerSensor.h`) — Acelerómetro dedicado (deprecado: usar MPU6050).
4. **LoadSensor** (`LoadSensor.h`) — Sensor de carga (HX711 + celda de carga) entrega gramos; Modbus expone centi‑kg.

Los sensores 2–4 son stubs con modo MOCK para desarrollo sin hardware.

## Configuración por compilación

Define en `platformio.ini` (sección `build_flags`) qué sensores activar:

```ini
build_flags =
  -DSENSORS_MPU_ENABLED=1       ; Habilita MPU6050
  -DSENSORS_TEMP_ENABLED=0      ; Deshabilita temperatura
  -DSENSORS_ACCEL_ENABLED=0     ; Deshabilita acelerómetro dedicado
  -DSENSORS_LOAD_ENABLED=0      ; Deshabilita sensor de carga
  -DSENSORS_USE_MOCK=0          ; 0=HW real, 1=datos sintéticos
```

Solo se compilan e instancian los sensores habilitados, ahorrando RAM/Flash.

## Uso desde main.cpp

```cpp
#include <SensorManager.h>
#include <SensorConfig.h>
#if SENSORS_MPU_ENABLED
#include <MPU6050Sensor.h>
#endif
// ... incluir otros sensores habilitados ...

static SensorManager sensorManager;
#if SENSORS_MPU_ENABLED
static MPU6050Sensor sensor_mpu0;
#endif

void setup(){
  // ... Modbus + BlinkIdent ...
#if SENSORS_MPU_ENABLED
  sensorManager.registerSensor(&sensor_mpu0);
#endif
  sensorManager.beginAll();
}

void loop(){
  // ... Modbus + BlinkIdent ...
  sensorManager.pollAll(millis());
}
```

**Ventaja**: `main.cpp` permanece simple; cambiar configuración de sensores solo requiere editar `platformio.ini`.

## Añadir un nuevo tipo de sensor

1. Crear `MiSensor.h` implementando `ISensor` y devolver `TelemetryDelta` con los campos disponibles.
2. Añadir en `SensorConfig.h` una macro `SENSORS_MISENSOR_ENABLED` con default 0.
3. Condicionar include y registro en `main.cpp` con `#if SENSORS_MISENSOR_ENABLED`.
4. Activar en `platformio.ini` con `-DSENSORS_MISENSOR_ENABLED=1`.

### Esqueleto

```cpp
class MiSensor : public ISensor {
 public:
  const char* name() const override { return "MiSensor"; }
  SensorKind kind() const override { return SensorKind::Unknown; }
  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true; return true;
#else
    // TODO: inicializar HW real
    available_ = false; return false;
#endif
  }
  bool poll(uint32_t nowMs, TelemetryDelta& out) override {
    if (!available_) return false;
    if ((uint32_t)(nowMs - last_ms_) < sample_interval_ms_) return false;
    last_ms_ = nowMs;
    out = TelemetryDelta{};
#if SENSORS_USE_MOCK
    out.temp_mc = 2500; // ejemplo
    out.has_temp = true;
#endif
    out.bump_sample = true;
    return true;
  }
  bool isAvailable() const override { return available_; }
 private:
  uint16_t sample_interval_ms_ = 500;
  uint32_t last_ms_ = 0;
  bool available_ = false;
};
```

## Normalización de unidades

- Acelerómetro: **mg** (1 g = 1000 mg)
- Giroscopio: **mdps** (1°/s = 1000 mdps)
- Ángulos: **mdeg** (1° = 10 mdeg)
- Temperatura: **mc** (1°C = 100 mc)
- Peso: los sensores reportan **g** en `TelemetryDelta.load_g`; el `SensorManager` lo convierte y publica en Modbus como **centi‑kg** (0.01 kg) en `IR_MED_PESO_KG_CENTI`.

## Flujo de datos

1. `SensorManager.pollAll(millis())` itera sensores registrados.
2. Cada sensor con `isAvailable()==true` ejecuta `poll(nowMs, out)`.
3. Si `poll()` devuelve `true`, el manager llama a `applyTelemetry(out)`.
4. `applyTelemetry()` escribe en registros Modbus vía `regs_set_*` solo los campos con flags `has_*` activos.
5. El contador de muestras se incrementa si `bump_sample==true`.

## Modo MOCK

Compilar con `-DSENSORS_USE_MOCK=1` genera datos sintéticos sin hardware. Útil para:
- Probar edge/MQTT sin sensores físicos.
- Validar arquitectura Modbus sin I²C/SPI.
- Demos y desarrollo rápido.

## Notas

- `SensorManager` mantiene máximo 4 sensores (`MAX_SENSORS`); ajustar si se necesitan más.
- `main.cpp` no contiene lógica de sensores; toda la captura está en `Sensors/`.
- Cada sensor controla su propio intervalo de muestreo; el manager no hace throttling global.

