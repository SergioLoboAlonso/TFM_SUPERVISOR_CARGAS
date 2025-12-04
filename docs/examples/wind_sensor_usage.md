# Uso del Sensor de Viento

## Integración en `main.cpp`

Para habilitar el sensor de viento en tu dispositivo:

### 1. Configurar `platformio.ini`

```ini
[env:uno]
platform = atmelavr
board = uno
framework = arduino
build_flags = 
  -DSENSORS_MPU_ENABLED=1
  -DSENSORS_WIND_ENABLED=1       ; Habilita sensor de viento analógico
  -DWIND_SPEED_ANALOG_PIN=A0     ; Pin analógico del anemómetro
  -DWIND_VOLT_MIN=0.40           ; Voltaje mínimo ≈ 0 m/s
  -DWIND_VOLT_MAX=2.00           ; Voltaje máximo ≈ 32.4 m/s
  -DWIND_SPEED_MAX=32.40         ; Velocidad máxima nominal (m/s)
  -DWIND_ADC_REF_V=5.00          ; Referencia ADC
  -DWIND_SAMPLES_AVG=4           ; Lecturas para promedio
  -DSENSORS_USE_MOCK=0           ; Usar hardware real
```

### 2. Modificar `main.cpp`

```cpp
#include <Arduino.h>
#include "config_pins.h"
#include <BlinkIdent.h>
#include <ModbusRTU.h>
#include <registersModbus.h>
#include <EepromUtils.h>
#include <SensorManager.h>
#include <SensorConfig.h>

#if SENSORS_MPU_ENABLED
#include <MPU6050Sensor.h>
#endif

#if SENSORS_WIND_ENABLED
#include <WindSpeedSensor.h>
#endif

static BlinkIdent ident(IDENT_LED_PIN);
static ModbusRTU modbus_client;
static SensorManager sensorManager;

#if SENSORS_MPU_ENABLED
static MPU6050Sensor sensor_mpu0;
#endif

#if SENSORS_WIND_ENABLED
static WindSpeedSensor sensor_wind0; // analógico
#endif

void setup() {
  // ... (código existente de Serial, LED, UART, Modbus, BlinkIdent) ...
  
  // Registrar sensores
#if SENSORS_MPU_ENABLED
  sensorManager.registerSensor(&sensor_mpu0);
#endif

  #if SENSORS_WIND_ENABLED
  sensorManager.registerSensor(&sensor_wind0);
  #endif

  sensorManager.beginAll();
  
  // Anemómetro analógico no requiere interrupciones
}

void loop() {
  modbus_client.poll();
  apply_ident_from_register();
  ident.update();
  
  // ... (código existente de guardar/aplicar config) ...
  
  sensorManager.pollAll(millis());
}
```

## Calibración del Anemómetro Analógico

El fabricante especifica el rango: 0.4–2.0 V → 0–32.4 m/s.

Fórmula lineal interna:

```
speed_mps = (V - V_MIN) * (SPEED_MAX / (V_MAX - V_MIN))
```

Para refinar:
1. Mide con multímetro el voltaje a varias velocidades conocidas (ventilador, túnel, referencia comercial).
2. Ajusta `WIND_VOLT_MIN` si el anemómetro no baja realmente a 0.40 V en reposo.
3. Ajusta `WIND_VOLT_MAX` si a la máxima velocidad el voltaje no llega a 2.00 V.
4. Si la curva no es perfectamente lineal, define una tabla y reemplaza el cálculo directo por interpolación.

## Registros Modbus

El sensor expone un registro de velocidad y deja dirección en cero (sin veleta):

| Registro | Dirección PDU | Ref | Descripción | Unidad |
|----------|---------------|-----|-------------|--------|
| Velocidad viento | 0x000D | 30014 | Velocidad en cm/s | m/s × 100 |
| Dirección viento (sin veleta) | 0x000E | 30015 | 0 fijo | grados |

**Ejemplo de lectura Edge/Python**:

```python
# Leer velocidad del viento (dirección siempre 0)
result = client.read_input_registers(address=0x000D, count=2, slave=unit_id)
if not result.isError():
  wind_speed_cmps = result.registers[0]
  wind_speed_mps = wind_speed_cmps / 100.0
  print(f"Viento: {wind_speed_mps:.2f} m/s")
```

## Modo MOCK (pruebas sin hardware)

Para desarrollar sin hardware físico:

```ini
build_flags = 
  -DSENSORS_WIND_ENABLED=1
  -DSENSORS_USE_MOCK=1  ; Genera datos sintéticos
```

Datos mock:
- Velocidad: onda senoidal 0-10 m/s
- Dirección: rotación continua 0-359°

## Troubleshooting

### Lecturas erráticas
- Revisa estabilidad de alimentación (usar 5V regulado)
- Añade un condensador de desacoplo (100nF) cerca del sensor
- Promedia más muestras (`WIND_SAMPLES_AVG`)

### Valores saturados (siempre máximos)
- Verifica que `WIND_VOLT_MAX` corresponda a tu máximo medido real
- Comprueba que el sensor no esté recibiendo voltaje >2.0V

### Velocidad siempre 0 m/s
- Cable señal desconectado
- Voltaje base <0.4V: ajusta `WIND_VOLT_MIN`
- Pin incorrecto: confirma `WIND_SPEED_ANALOG_PIN`

