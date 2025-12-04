# AngleCalculator

Calculador de ángulos de inclinación (Pitch y Roll) a partir de datos del acelerómetro.

## Características

- ✅ Cálculo de Pitch (inclinación adelante/atrás) y Roll (inclinación lateral)
- ✅ Filtro exponencial móvil (EMA) configurable
- ✅ Salida en décimas de grado (mdeg) compatible con `registersModbus.h`
- ✅ Sin dependencias externas (solo math.h)
- ⚠️ Solo usa acelerómetro (no fusiona con giroscopio)

## Uso básico

```cpp
#include <AngleCalculator.h>
#include <MPU6050Driver.h>

MPU6050Driver mpu(0x68);
AngleCalculator angles;

void setup() {
  mpu.begin();
  
  // Configurar filtro opcional (0.0 = sin filtro, 0.9 = muy suave)
  angles.setFilterAlpha(0.3f);  // Filtrado moderado
}

void loop() {
  int16_t ax, ay, az;
  if (mpu.readAccelMg(ax, ay, az)) {
    // Actualizar ángulos
    angles.update(ax, ay, az);
    
    // Leer ángulos en décimas de grado (mdeg)
    int16_t pitch = angles.getPitchMdeg();  // Inclinación X
    int16_t roll = angles.getRollMdeg();    // Inclinación Y
    
    // Ejemplo: pitch = 450 significa 45.0°
  }
  
  delay(100);
}
```

## API

### Actualización
- `void update(int16_t acc_x_mg, int16_t acc_y_mg, int16_t acc_z_mg)` — Calcula ángulos a partir de aceleración en mg

### Lectura de ángulos
- `int16_t getPitchMdeg()` — Ángulo Pitch en décimas de grado
- `int16_t getRollMdeg()` — Ángulo Roll en décimas de grado

### Configuración
- `void setFilterAlpha(float alpha)` — Coeficiente de filtro EMA (0.0-1.0)
- `void reset()` — Reinicia ángulos a cero

## Definición de ángulos

### Pitch (ángulo X)
- Rotación alrededor del eje Y
- Inclinación **adelante/atrás**
- Positivo: nariz hacia abajo
- Negativo: nariz hacia arriba
- Fórmula: `atan2(acc_x, sqrt(acc_y² + acc_z²))`

### Roll (ángulo Y)
- Rotación alrededor del eje X
- Inclinación **izquierda/derecha**
- Positivo: inclinación hacia la derecha
- Negativo: inclinación hacia la izquierda
- Fórmula: `atan2(acc_y, sqrt(acc_x² + acc_z²))`

## Sistema de referencia

```
        +Y (Roll)
         |
         |
         +---- +X (Pitch)
        /
       /
      +Z (gravedad cuando horizontal)
```

### Ejemplos de orientación

| Orientación               | Pitch | Roll | Accel X | Accel Y | Accel Z |
|---------------------------|-------|------|---------|---------|---------|
| Horizontal (flat)         | 0°    | 0°   | 0 mg    | 0 mg    | 1000 mg |
| 45° hacia adelante        | +45°  | 0°   | 707 mg  | 0 mg    | 707 mg  |
| 45° hacia atrás           | -45°  | 0°   | -707 mg | 0 mg    | 707 mg  |
| 45° hacia la derecha      | 0°    | +45° | 0 mg    | 707 mg  | 707 mg  |
| 45° hacia la izquierda    | 0°    | -45° | 0 mg    | -707 mg | 707 mg  |
| Vertical (nariz arriba)   | -90°  | 0°   | -1000mg | 0 mg    | 0 mg    |
| Vertical (nariz abajo)    | +90°  | 0°   | 1000 mg | 0 mg    | 0 mg    |

## Filtro exponencial móvil (EMA)

### Fórmula
```
filtered = old + alpha × (new - old)
```

### Parámetro alpha

| Alpha | Comportamiento            | Uso recomendado          |
|-------|---------------------------|--------------------------|
| 0.0   | Sin filtro (instantáneo)  | Respuesta muy rápida     |
| 0.1   | Filtrado muy ligero       | Sensor con bajo ruido    |
| 0.2-0.3 | Filtrado moderado       | **Recomendado (general)**|
| 0.5   | Filtrado medio            | Compromiso suavidad/lag  |
| 0.7-0.9 | Filtrado fuerte         | Mucho ruido              |
| 1.0   | Sin cambio (bloqueado)    | No usar                  |

**Recomendación**: `alpha = 0.3` para inclinómetro con buena respuesta y suavizado.

### Efecto del filtro

- **Alpha bajo (0.1)**: Muy suave pero lento para seguir cambios rápidos
- **Alpha alto (0.9)**: Rápido pero ruidoso
- **Sin filtro (0.0)**: Respuesta instantánea, valores ruidosos

## Limitaciones

### Solo acelerómetro
- ✅ Bueno para: inclinación estática (lenta), medición de gravedad
- ❌ Malo para: movimientos rápidos, rotaciones dinámicas, vibración

### Ruido y vibración
- Vibraciones pueden causar lecturas erróneas (la aceleración vibratoria se suma a la gravedad)
- Solución: usar filtro DLPF en MPU6050 + EMA en AngleCalculator

### Gimbal lock
- Cerca de ±90° en Pitch, el Roll puede volverse inestable
- No es problema para inclinómetro típico (±45°)

## Mejoras futuras

### Filtro complementario (fusión accel + gyro)
```cpp
// Combinar accel (baja frecuencia) con gyro (alta frecuencia)
pitch_filtered = 0.98 * (pitch_gyro_integrated) + 0.02 * (pitch_accel);
```

### Filtro de Kalman
- Fusión óptima de sensores
- Reduce ruido y deriva
- Mayor complejidad computacional

## Referencias

- [Freescale AN3461: Tilt Sensing Using Accelerometer](https://www.nxp.com/docs/en/application-note/AN3461.pdf)
- [Complementary Filter Design](https://www.pieter-jan.com/node/11)
