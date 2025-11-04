// -----------------------------------------------------------------------------
// LoadSensor.h — Sensor de carga/peso con HX711 (celda de carga)
// Mide peso/carga en gramos (g) con celda de carga y amplificador HX711.
// Requiere librería HX711 (https://github.com/bogde/HX711)
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include "SensorConfig.h"

#if !SENSORS_USE_MOCK
#include <HX711.h>
#endif

// Pines por defecto para HX711; pueden sobreescribirse desde platformio.ini
#ifndef HX711_DOUT_PIN
#define HX711_DOUT_PIN 5
#endif

#ifndef HX711_SCK_PIN
#define HX711_SCK_PIN 6
#endif

// Factor de calibración por defecto (ajustar según celda de carga)
// Típico: ~400-450 para celdas de 1-5kg; obtener con calibración manual
#ifndef HX711_CALIBRATION_FACTOR
#define HX711_CALIBRATION_FACTOR 420.0f
#endif

class LoadSensor : public ISensor {
public:
  explicit LoadSensor(uint8_t dout_pin = HX711_DOUT_PIN, 
                      uint8_t sck_pin = HX711_SCK_PIN,
                      uint16_t sample_interval_ms = 200)
  : sample_interval_ms_(sample_interval_ms)
#if !SENSORS_USE_MOCK
      , scale_()
#endif
  {
#if !SENSORS_USE_MOCK
    dout_pin_ = dout_pin;
    sck_pin_ = sck_pin;
#else
    (void)dout_pin; (void)sck_pin; // Evitar warnings
#endif
  }

  const char* name() const override { return "LoadSensor"; }
  SensorKind kind() const override { return SensorKind::Load; }

  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true;
    last_ms_ = millis();
    return true;
#else
    scale_.begin(dout_pin_, sck_pin_);
    
    // Verificar que HX711 responde
    if (!scale_.is_ready()) {
      available_ = false;
      return false;
    }
    
    // Configurar ganancia (128 para canal A típicamente)
    scale_.set_gain(128);
    
    // Aplicar factor de calibración
    scale_.set_scale(HX711_CALIBRATION_FACTOR);
    
    // Leer valor inicial sin tara (para verificar comunicación)
    scale_.read();
    
    // Hacer tara inicial (asume que no hay peso al inicio)
    scale_.tare(5); // Promedio de 5 lecturas
    
    available_ = true;
    last_ms_ = millis();
    return true;
#endif
  }

  bool poll(uint32_t nowMs, TelemetryDelta& out) override {
    if (!available_) return false;
    if ((uint32_t)(nowMs - last_ms_) < sample_interval_ms_) return false;
    
    out = TelemetryDelta{};
    
#if SENSORS_USE_MOCK
    // Simular peso variable entre 0 y 5 kg con ruido
    static int16_t phase = 0; 
    phase = (phase + 7) % 360;
    float weight_kg = 2.5f + 2.0f * sinf(phase * 0.0174533f) + (random(-50, 50) / 100.0f);
    out.load_g = (int16_t)(weight_kg * 1000.0f); // Convertir kg a gramos
    last_ms_ = nowMs;
#else
    // Verificar que HX711 está listo
    if (!scale_.is_ready()) {
      return false;
    }
    
    // Leer peso (promedio de 3 lecturas para estabilidad)
    float weight_grams = scale_.get_units(3);
    
    // Validar rango razonable (±32 kg)
    if (weight_grams < -32000.0f || weight_grams > 32000.0f) {
      // Fuera de rango; posible error de lectura
      return false;
    }
    
    out.load_g = (int16_t)weight_grams;
    last_ms_ = nowMs;
#endif
    
    out.has_load = true;
    out.bump_sample = true;
    return true;
  }

  bool isAvailable() const override { return available_; }

#if !SENSORS_USE_MOCK
  // Métodos de utilidad para calibración y control
  
  // Hacer tara (establecer cero actual como referencia)
  void tare(uint8_t times = 10) {
    if (available_) {
      scale_.tare(times);
    }
  }
  
  // Ajustar factor de calibración
  void setCalibrationFactor(float factor) {
    calibration_factor_ = factor;
    scale_.set_scale(factor);
  }
  
  float getCalibrationFactor() const {
    return calibration_factor_;
  }
  
  // Leer peso raw (sin escalar) para calibración
  long readRaw() {
    return scale_.read();
  }
  
  // Obtener peso en gramos directamente
  float getWeightGrams(uint8_t times = 1) {
    return scale_.get_units(times);
  }
#endif

private:
  uint16_t sample_interval_ms_;
  uint32_t last_ms_ = 0;
  bool available_ = false;
  
#if !SENSORS_USE_MOCK
  HX711 scale_;
  uint8_t dout_pin_;
  uint8_t sck_pin_;
  float calibration_factor_ = HX711_CALIBRATION_FACTOR;
#endif
};
