# MPU6050Driver

Driver I²C para el sensor MPU-6050 (acelerómetro + giroscopio de 6 ejes).

## Características

- ✅ Comunicación I²C nativa (Wire.h)
- ✅ Lectura de acelerómetro (3 ejes) en mg (mili-g)
- ✅ Lectura de giroscopio (3 ejes) en mdps (mili-grados por segundo)
- ✅ Lectura de temperatura en centésimas de °C
- ✅ Configuración de rangos dinámicos (accel: ±2/4/8/16g, gyro: ±250/500/1000/2000°/s)
- ✅ Configuración de filtro pasa-bajos digital (DLPF)
- ✅ Compatibilidad con unidades de `registersModbus.h`
- ⚠️ Calibración de offsets (placeholder, no implementado)

## Uso básico

```cpp
#include <MPU6050Driver.h>

MPU6050Driver mpu(0x68);  // Dirección I²C (0x68 si AD0=GND)

void setup() {
  if (!mpu.begin()) {
    // Error de inicialización
    return;
  }
  
  // Configuración opcional
  mpu.setAccelRange(ACCEL_RANGE_2G);     // ±2g
  mpu.setGyroRange(GYRO_RANGE_250DPS);   // ±250°/s
  mpu.setDLPF(3);                        // Filtro 42 Hz
}

void loop() {
  int16_t ax, ay, az;
  if (mpu.readAccelMg(ax, ay, az)) {
    // ax, ay, az en mili-g (mg)
  }
  
  int16_t gx, gy, gz;
  if (mpu.readGyroMdps(gx, gy, gz)) {
    // gx, gy, gz en mili-grados por segundo (mdps)
  }
  
  int16_t temp_mc = mpu.readTempCenti();
  // temp_mc en centésimas de °C
  
  delay(100);
}
```

## API

### Inicialización
- `bool begin()` — Inicializa el sensor y verifica WHO_AM_I
- `bool isConnected()` — Verifica conectividad I²C

### Lecturas escaladas (recomendado)
- `bool readAccelMg(int16_t& x, int16_t& y, int16_t& z)` — Lee aceleración en mg
- `bool readGyroMdps(int16_t& x, int16_t& y, int16_t& z)` — Lee velocidad angular en mdps
- `int16_t readTempCenti()` — Lee temperatura en centésimas de °C

### Lecturas raw
- `bool readRawAccel(int16_t& x, int16_t& y, int16_t& z)` — Valores de 16 bits directos
- `bool readRawGyro(int16_t& x, int16_t& y, int16_t& z)`
- `bool readRawTemp(int16_t& temp)`

### Configuración
- `void setAccelRange(AccelRange range)` — Rango del acelerómetro
- `void setGyroRange(GyroRange range)` — Rango del giroscopio
- `void setDLPF(uint8_t mode)` — Filtro pasa-bajos (0-6)

## Conexión hardware

### Pines I²C (UNO/NANO)
- **SDA**: A4
- **SCL**: A5
- **VCC**: 3.3V o 5V (módulo con regulador)
- **GND**: GND
- **AD0**: GND (dirección 0x68) o VCC (dirección 0x69)

### Notas
- Módulo GY-521 típicamente incluye pull-ups de 4.7kΩ en SDA/SCL
- Si AD0 queda flotante puede causar problemas de comunicación
- Velocidad I²C configurada a 400 kHz (Fast Mode)

## Conversiones de unidades

### Acelerómetro (mg = mili-g)
- 1g = 1000 mg
- Gravedad terrestre ≈ 9.8 m/s² ≈ 1000 mg
- Sensor horizontal en reposo: Z ≈ ±1000 mg, X ≈ 0, Y ≈ 0

### Giroscopio (mdps = mili-grados por segundo)
- 1°/s = 1000 mdps
- Sensor inmóvil: todos los ejes ≈ 0 mdps
- Rotación completa (360°) en 1 segundo = 360000 mdps

### Temperatura (mc = centésimas de °C)
- 25.5°C = 2550 mc
- Fórmula: `Temp_°C = (raw / 340.0) + 36.53`

## Rangos y sensibilidades

| Rango Accel | Sensibilidad | mg/LSB |
|-------------|--------------|--------|
| ±2g         | 16384 LSB/g  | 0.061  |
| ±4g         | 8192 LSB/g   | 0.122  |
| ±8g         | 4096 LSB/g   | 0.244  |
| ±16g        | 2048 LSB/g   | 0.488  |

| Rango Gyro  | Sensibilidad     | mdps/LSB |
|-------------|------------------|----------|
| ±250°/s     | 131 LSB/(°/s)    | 7.633    |
| ±500°/s     | 65.5 LSB/(°/s)   | 15.267   |
| ±1000°/s    | 32.8 LSB/(°/s)   | 30.488   |
| ±2000°/s    | 16.4 LSB/(°/s)   | 60.976   |

## Filtro DLPF

| Modo | Freq. Accel | Freq. Gyro | Uso recomendado |
|------|-------------|------------|-----------------|
| 0    | ~260 Hz     | ~256 Hz    | Sin filtrado    |
| 1    | 184 Hz      | 188 Hz     | Mínimo filtrado |
| 2    | 94 Hz       | 98 Hz      | Ligero          |
| **3**| **44 Hz**   | **42 Hz**  | **Recomendado** |
| 4    | 21 Hz       | 20 Hz      | Moderado        |
| 5    | 10 Hz       | 10 Hz      | Fuerte          |
| 6    | 5 Hz        | 5 Hz       | Muy fuerte      |

**Recomendación**: Modo 3 (42 Hz) es un buen compromiso entre reducción de ruido y latencia para aplicaciones de inclinómetro.

## Referencias

- [MPU-6000/6050 Register Map (Rev. 4.2)](https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf)
- [MPU-6050 Product Specification](https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf)
