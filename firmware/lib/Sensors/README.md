# Sensors module

Abstracción y orquestación de sensores para el firmware. Evita lógica en `main.cpp` y normaliza la telemetría a las unidades del contrato Modbus.

## Componentes

- `ISensor.h` — Interfaz base de sensores (begin, poll, isAvailable).
- `SensorTypes.h` — Tipos normalizados de telemetría (mg, mdps, mdeg, mc) y enumeración de sensores.
- `SensorConfig.h` — Configuración por compilación (habilitación de sensores, cuentas, modo MOCK).
- `SensorManager.h/.cpp` — Orquestador que registra, inicializa, hace poll no bloqueante y vuelca a registros Modbus vía `regs_set_*`.

### Sensores disponibles

1. **MPU6050Sensor** (`MPU6050Sensor.h`) — **Sensor unificado IMU**: provee acelerómetro (3-ejes en mg), giroscopio (3-ejes en mdps), temperatura interna (en mc/centi-°C) y ángulos de inclinación pitch/roll (en cdeg). **Es el sensor principal para telemetría de inclinación y orientación.**
2. **LoadSensor** (`LoadSensor.h`) — Sensor de carga (HX711 + celda de carga) entrega gramos; Modbus expone centi‑kg.
3. **WindSpeedSensor** (`WindSpeedSensor.h`) — Anemómetro analógico (Adafruit 0–32.4 m/s, salida 0.4–2.0V). Se convierte linealmente a velocidad (m/s) y se expone como cm/s en Modbus. No incluye dirección (no hay veleta instalada).

**NOTA**: Los sensores dedicados `AccelerometerSensor` y `TemperatureSensor` han sido **eliminados** por redundancia. MPU6050 ya provee aceleración (superior a un acelerómetro mock) y temperatura interna (suficiente para la mayoría de aplicaciones). Si necesitas temperatura ambiente precisa (DS18B20), restaura `TemperatureSensor.h` desde el historial de Git.

## Configuración por compilación

Define en `platformio.ini` (sección `build_flags`) qué sensores activar:

```ini
build_flags =
  -DSENSORS_MPU_ENABLED=1       ; Habilita MPU6050 (accel + gyro + temp + ángulos)
  -DSENSORS_LOAD_ENABLED=0      ; Deshabilita sensor de carga
  -DSENSORS_WIND_ENABLED=0      ; Deshabilita sensor de viento
  -DSENSORS_USE_MOCK=0          ; 0=HW real, 1=datos sintéticos
  
  ; Calibración anemómetro analógico (si SENSORS_WIND_ENABLED=1)
  -DWIND_SPEED_ANALOG_PIN=A0    ; Pin analógico lectura tensión anemómetro
  -DWIND_VOLT_MIN=0.40          ; Voltaje mínimo (≈0 m/s)
  -DWIND_VOLT_MAX=2.00          ; Voltaje máximo (≈32.4 m/s)
  -DWIND_SPEED_MAX=32.40        ; Velocidad máxima nominal (m/s)
  -DWIND_ADC_REF_V=5.00         ; Referencia ADC (tip. 5V)
  -DWIND_SAMPLES_AVG=4          ; Promedio lecturas para suavizado
```

Solo se compilan e instancian los sensores habilitados, ahorrando RAM/Flash.

**NOTA**: Los flags `SENSORS_TEMP_ENABLED` y `SENSORS_ACCEL_ENABLED` están deprecados (sensores eliminados).

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

