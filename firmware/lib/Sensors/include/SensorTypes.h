// -----------------------------------------------------------------------------
// SensorTypes.h — Tipos comunes para normalizar telemetría de sensores
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include <stdint.h>

// Telemetría normalizada en unidades del contrato Modbus
// - Ángulos: mdeg (décimas de grado)
// - Aceleraciones: mg (mili-g)
// - Giros: mdps (mili-grados/seg)
// - Temperatura: mc (centésimas de °C)
// - Peso/Carga: gramos (g) — para precisión con int16_t (rango ±32.767 kg)
// - Corriente: miliamperios (mA)
struct TelemetryDelta {
  // Flags de presencia para escritura selectiva
  bool has_angles = false;
  bool has_accel  = false;
  bool has_gyro   = false;
  bool has_temp   = false;
  bool has_load   = false;  // Peso/carga en gramos
  bool has_current= false;  // Corriente eléctrica en mA
  bool bump_sample= false;  // Solicita incrementar contador de muestras

  // Ángulos (mdeg)
  int16_t pitch_mdeg = 0;
  int16_t roll_mdeg  = 0;

  // Acelerómetro (mg)
  int16_t acc_x_mg = 0;
  int16_t acc_y_mg = 0;
  int16_t acc_z_mg = 0;

  // Giroscopio (mdps)
  int16_t gyr_x_mdps = 0;
  int16_t gyr_y_mdps = 0;
  int16_t gyr_z_mdps = 0;

  // Temperatura (mc)
  int16_t temp_mc = 0;
  
  // Carga/Peso (gramos, rango ±32.767 kg con precisión de 1g)
  int16_t load_g = 0;
  
  // Corriente eléctrica (mA, rango ±32.767 A con precisión de 1mA)
  int16_t current_ma = 0;
};

// Opcional: tipo de sensor, por si se requiere reportar capacidades
enum class SensorKind : uint8_t {
  Unknown = 0,
  InclinometerIMU = 1,
  Temperature     = 2,
  Current         = 3,
  Voltage         = 4,
  Accelerometer   = 5,
  Load            = 6,
};
