// -----------------------------------------------------------------------------
// AngleCalculator.h — Cálculo de ángulos de inclinación desde acelerómetro
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
//
// Responsabilidades
// - Calcular ángulos Pitch (X) y Roll (Y) a partir de acelerómetro
// - Aplicar filtrado opcional para suavizar medidas
// - Conversión a unidades compatibles con registersModbus (mdeg = décimas de grado)
//
// Método de cálculo
// - Pitch (ángulo respecto al eje X): atan2(acc_x, sqrt(acc_y² + acc_z²))
// - Roll (ángulo respecto al eje Y):  atan2(acc_y, sqrt(acc_x² + acc_z²))
// - Rango típico: -180° a +180° (o -90° a +90° para inclinómetro simple)
//
// Notas de implementación
// - Solo usa acelerómetro (estático); no fusiona con giroscopio (sin filtro complementario)
// - Filtro opcional: exponencial móvil (EMA) con parámetro alpha
// - Compatibilidad con registersModbus: valores en décimas de grado (mdeg)
// - No requiere librerías externas (solo math.h para atan2)
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>
#include <math.h>
#include <stdint.h>

// -----------------------------
// Clase AngleCalculator
// -----------------------------
class AngleCalculator {
public:
  /**
   * @brief Constructor del calculador de ángulos
   * 
   * Inicializa los ángulos a cero y configura filtrado desactivado por defecto
   */
  AngleCalculator();

  /**
   * @brief Actualiza los ángulos a partir de aceleración en mg
   * 
   * Calcula Pitch y Roll usando las componentes del acelerómetro:
   * - Pitch (ángulo X): rotación alrededor del eje Y (inclinación adelante/atrás)
   * - Roll (ángulo Y): rotación alrededor del eje X (inclinación izquierda/derecha)
   * 
   * Fórmulas:
   * - Pitch = atan2(acc_x, sqrt(acc_y² + acc_z²)) * (180/π)
   * - Roll  = atan2(acc_y, sqrt(acc_x² + acc_z²)) * (180/π)
   * 
   * @param acc_x_mg Aceleración en eje X en mili-g (mg)
   * @param acc_y_mg Aceleración en eje Y en mili-g (mg)
   * @param acc_z_mg Aceleración en eje Z en mili-g (mg)
   * 
   * @note Los valores de entrada provienen de MPU6050Driver::readAccelMg()
   * @note Aplica filtro exponencial si está habilitado (alpha > 0)
   */
  void update(int16_t acc_x_mg, int16_t acc_y_mg, int16_t acc_z_mg);

  /**
   * @brief Obtiene el ángulo Pitch en centésimas de grado (cdeg)
   * 
   * Pitch es la rotación alrededor del eje Y (inclinación adelante/atrás)
   * - Valor positivo: inclinación hacia adelante (nariz hacia abajo)
   * - Valor negativo: inclinación hacia atrás (nariz hacia arriba)
   * 
   * @return Ángulo Pitch en centésimas de grado (cdeg = 0.01°)
   * 
   * @note Compatible con regs_set_angles_mdeg(pitch, roll)
   * @note Rango típico: -9000 a +9000 cdeg (-90° a +90°)
   */
  int16_t getPitchMdeg() const { return pitch_mdeg_; }

  /**
   * @brief Obtiene el ángulo Roll en centésimas de grado (cdeg)
   * 
   * Roll es la rotación alrededor del eje X (inclinación izquierda/derecha)
   * - Valor positivo: inclinación hacia la derecha
   * - Valor negativo: inclinación hacia la izquierda
   * 
   * @return Ángulo Roll en centésimas de grado (cdeg = 0.01°)
   * 
   * @note Compatible con regs_set_angles_mdeg(pitch, roll)
   * @note Rango típico: -9000 a +9000 cdeg (-90° a +90°)
   */
  int16_t getRollMdeg() const { return roll_mdeg_; }

  /**
   * @brief Configura el coeficiente del filtro exponencial móvil (EMA)
   * 
   * El filtro EMA suaviza las medidas con la fórmula:
   *   filtered = alpha * new_value + (1 - alpha) * old_value
   * 
   * @param alpha Coeficiente de filtrado (0.0 a 1.0):
   *   - 0.0: filtro desactivado (sin suavizado, respuesta instantánea)
   *   - 0.1-0.3: filtrado ligero (buena respuesta, poco suavizado)
   *   - 0.5-0.7: filtrado moderado (compromiso entre respuesta y suavizado)
   *   - 0.9-0.99: filtrado fuerte (muy suave pero lento)
   * 
   * @note Recomendado: 0.2-0.3 para inclinómetro con buena respuesta
   * @note Mayor alpha = más suave pero más latencia
   */
  void setFilterAlpha(float alpha);

  /**
   * @brief Reinicia los ángulos a cero
   * 
   * Útil para reiniciar el estado del calculador (por ejemplo, después de recalibrar)
   */
  void reset();

private:
  /**
   * @brief Convierte grados a centésimas de grado (cdeg)
   * 
   * @param degrees Ángulo en grados
   * @return Ángulo en centésimas de grado (cdeg = 0.01°)
   */
  int16_t degreesToCdeg(float degrees) const;

  /**
   * @brief Aplica el filtro exponencial móvil a un valor
   * 
   * @param new_value Nuevo valor medido
   * @param old_value Valor filtrado anterior
   * @return Valor filtrado actualizado
   */
  float applyFilter(float new_value, float old_value) const;

  // -----------------------------
  // Atributos privados
  // -----------------------------
  int16_t pitch_mdeg_;     // Ángulo Pitch en centésimas de grado (cdeg)
  int16_t roll_mdeg_;      // Ángulo Roll en centésimas de grado (cdeg)
  float filter_alpha_;     // Coeficiente de filtrado EMA (0.0 = sin filtro)
  
  // Valores filtrados previos (en grados, para mayor precisión interna)
  float pitch_deg_filtered_;
  float roll_deg_filtered_;
  bool first_update_;      // Flag para primera actualización (sin filtro)
};
