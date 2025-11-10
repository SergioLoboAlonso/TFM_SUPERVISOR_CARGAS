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
// - Viento velocidad: cm/s (centímetros/segundo) — para precisión con uint16_t (rango 0..327.67 m/s)
// - Viento dirección: grados (0-359, 0=Norte, 90=Este, 180=Sur, 270=Oeste)
struct TelemetryDelta {
  // Flags de presencia para escritura selectiva
  bool has_angles = false;
  bool has_accel  = false;
  bool has_gyro   = false;
  bool has_temp   = false;
  bool has_load   = false;  // Peso/carga en gramos
  bool has_current= false;  // Corriente eléctrica en mA
  bool has_wind   = false;  // Velocidad y dirección del viento
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
  
  // Viento (velocidad en cm/s, dirección en grados 0-359)
  uint16_t wind_speed_cmps = 0;  // Velocidad en cm/s (m/s * 100)
  uint16_t wind_dir_deg = 0;     // Dirección 0-359° (0=N, 90=E, 180=S, 270=W)
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
  WindSpeed       = 7,
};
