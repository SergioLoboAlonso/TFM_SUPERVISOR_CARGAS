// -----------------------------------------------------------------------------
// AngleCalculator.cpp — Implementación del cálculo de ángulos de inclinación
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
//
// Referencias
// - Freescale Semiconductor AN3461: "Tilt Sensing Using a Three-Axis Accelerometer"
// - Fórmulas estándar para cálculo de ángulos desde acelerómetro
// -----------------------------------------------------------------------------

#include "AngleCalculator.h"

// -----------------------------
// Constructor
// -----------------------------
AngleCalculator::AngleCalculator()
  : pitch_mdeg_(0),
    roll_mdeg_(0),
    filter_alpha_(0.0f),
    pitch_deg_filtered_(0.0f),
    roll_deg_filtered_(0.0f),
    first_update_(true)
{
}

// -----------------------------
// Actualización de ángulos
// -----------------------------
void AngleCalculator::update(int16_t acc_x_mg, int16_t acc_y_mg, int16_t acc_z_mg) {
  // Convertir de mg a g (gravedad = 1000 mg)
  float ax = acc_x_mg / 1000.0f;
  float ay = acc_y_mg / 1000.0f;
  float az = acc_z_mg / 1000.0f;
  
  // Calcular Pitch (inclinación adelante/atrás)
  // Pitch = atan2(ax, sqrt(ay² + az²))
  // Se usa atan2 para obtener el signo correcto en todos los cuadrantes
  float pitch_rad = atan2(ax, sqrt(ay * ay + az * az));
  float pitch_deg = pitch_rad * RAD_TO_DEG;
  
  // Calcular Roll (inclinación izquierda/derecha)
  // Roll = atan2(ay, sqrt(ax² + az²))
  float roll_rad = atan2(ay, sqrt(ax * ax + az * az));
  float roll_deg = roll_rad * RAD_TO_DEG;
  
  // Aplicar filtro si está habilitado
  if (first_update_) {
    // Primera actualización: sin filtro (inicializar valores)
    pitch_deg_filtered_ = pitch_deg;
    roll_deg_filtered_ = roll_deg;
    first_update_ = false;
  } else if (filter_alpha_ > 0.0f) {
    // Aplicar filtro exponencial móvil (EMA)
    pitch_deg_filtered_ = applyFilter(pitch_deg, pitch_deg_filtered_);
    roll_deg_filtered_ = applyFilter(roll_deg, roll_deg_filtered_);
  } else {
    // Sin filtro: usar valores directos
    pitch_deg_filtered_ = pitch_deg;
    roll_deg_filtered_ = roll_deg;
  }
  
  // Convertir a centésimas de grado (cdeg) y almacenar
  pitch_mdeg_ = degreesToCdeg(pitch_deg_filtered_);
  roll_mdeg_ = degreesToCdeg(roll_deg_filtered_);
}

// -----------------------------
// Configuración de filtro
// -----------------------------
void AngleCalculator::setFilterAlpha(float alpha) {
  // Validar rango [0.0, 1.0]
  if (alpha < 0.0f) {
    alpha = 0.0f;
  } else if (alpha > 1.0f) {
    alpha = 1.0f;
  }
  
  filter_alpha_ = alpha;
}

// -----------------------------
// Reset
// -----------------------------
void AngleCalculator::reset() {
  pitch_mdeg_ = 0;
  roll_mdeg_ = 0;
  pitch_deg_filtered_ = 0.0f;
  roll_deg_filtered_ = 0.0f;
  first_update_ = true;
}

// -----------------------------
// Métodos privados
// -----------------------------
int16_t AngleCalculator::degreesToCdeg(float degrees) const {
  // Convertir grados a centésimas de grado (cdeg)
  // 1° = 100 cdeg
  // Ejemplo: 45.67° = 4567 cdeg
  
  float cdeg_float = degrees * 100.0f;
  
  // Saturar a rango int16_t para evitar overflow
  // Rango: -32768 a +32767 cdeg → -327.68° a +327.67°
  if (cdeg_float > 32767.0f) {
    return 32767;
  } else if (cdeg_float < -32768.0f) {
    return -32768;
  }
  
  return (int16_t)cdeg_float;
}

float AngleCalculator::applyFilter(float new_value, float old_value) const {
  // Filtro exponencial móvil (EMA):
  // filtered = alpha * new + (1 - alpha) * old
  //
  // Equivalente a:
  // filtered = old + alpha * (new - old)
  //
  // Características:
  // - alpha cercano a 0: muy suave (lento)
  // - alpha cercano a 1: sin filtro (rápido)
  
  return old_value + filter_alpha_ * (new_value - old_value);
}
