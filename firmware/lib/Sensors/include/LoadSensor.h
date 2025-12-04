// -----------------------------------------------------------------------------
// LoadSensor.h — Sensor de carga HX711 (uso mínimo)
// Lectura en gramos (g) usando HX711 con factor de escala definido.
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

// Factor de calibración (definir vía build_flags si procede)
#ifndef HX711_CALIBRATION_FACTOR
#define HX711_CALIBRATION_FACTOR 420.0f
#endif

class LoadSensor : public ISensor {
public:
  explicit LoadSensor(uint8_t dout_pin = HX711_DOUT_PIN,
                      uint8_t sck_pin = HX711_SCK_PIN,
                      uint16_t sample_interval_ms = 100)
    : dout_pin_(dout_pin)
    , sck_pin_(sck_pin)
    , sample_interval_ms_(sample_interval_ms < 100 ? 100 : sample_interval_ms)
  {}

  const char* name() const override { return "LoadSensor"; }
  SensorKind kind() const override { return SensorKind::Load; }

  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true;
    last_ms_ = millis();
    return true;
#else
    scale_.begin(dout_pin_, sck_pin_);
    
    // Timeout para verificar si el HX711 responde (no bloquear si está desconectado)
    uint32_t start = millis();
    while (!scale_.is_ready() && (millis() - start) < 100) {
      delay(10);
    }
    
    if (!scale_.is_ready()) {
      available_ = false;
      return false;  // HX711 no detectado, sensor no disponible
    }
    
    // Configurar ganancia
    scale_.set_gain(128);
    
    // Aplicar factor de calibración desde platformio.ini
    scale_.set_scale(HX711_CALIBRATION_FACTOR);
    
    // Aplicar offset si está definido, sino hacer tare NO BLOQUEANTE
    #ifdef HX711_OFFSET
      scale_.set_offset((long)HX711_OFFSET);
    #else
      // Tare con timeout: intentar solo 3 lecturas en lugar de 10
      // Si falla, continuar igual (mejor un offset incorrecto que bloquear todo)
      if (scale_.is_ready()) {
        scale_.tare(3);
      }
    #endif
    
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
    // Mock: generar peso simulado
    static int16_t phase = 0;
    phase = (phase + 7) % 360;
    float weight_kg = 2.5f + 2.0f * sinf(phase * 0.0174533f);
    out.load_g = (int16_t)(weight_kg * 1000.0f);
    last_ms_ = nowMs;
#else
    // Verificar disponibilidad del HX711 sin bloquear
    if (!scale_.is_ready()) {
      last_ms_ = nowMs;  // Actualizar timestamp para reintentar más tarde
      return false;
    }
    
    // Leer peso en gramos con SOLO 1 lectura para minimizar bloqueo
    // En lugar de 5 promedios, usar 1 lectura rápida
    float grams = scale_.get_units(1);
    
    // Validar rango razonable
    if (grams < -32000.0f || grams > 32000.0f) {
      last_ms_ = nowMs;
      return false;
    }
    
    out.load_g = (int16_t)grams;
    last_ms_ = nowMs;
#endif
    
    out.has_load = true;
    out.bump_sample = true;
    return true;
  }

  bool isAvailable() const override { return available_; }

private:
#if !SENSORS_USE_MOCK
  HX711 scale_;
#endif
  uint8_t dout_pin_;
  uint8_t sck_pin_;
  uint16_t sample_interval_ms_;
  uint32_t last_ms_ = 0;
  bool available_ = false;
};
