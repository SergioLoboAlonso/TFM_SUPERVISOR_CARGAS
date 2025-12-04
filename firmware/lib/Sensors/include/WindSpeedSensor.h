// -----------------------------------------------------------------------------
// WindSpeedSensor.h — Sensor de velocidad del viento (ANALÓGICO)
// Adafruit 0–32.4 m/s, salida 0.4–2.0V → mapea linealmente a m/s
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include "SensorConfig.h"

// Pines por defecto; pueden sobreescribirse desde platformio.ini
#ifndef WIND_SPEED_ANALOG_PIN
#define WIND_SPEED_ANALOG_PIN A0   // Pin analógico para anemómetro
#endif

// Calibración del anemómetro ANALÓGICO Adafruit (0.4–2.0 V → 0–32.4 m/s)
// Fórmula lineal: speed_mps = (V - V_MIN) * (SPEED_MAX / (V_MAX - V_MIN))
#ifndef WIND_VOLT_MIN
#define WIND_VOLT_MIN 0.40f   // Voltaje mínimo (m/s ≈ 0)
#endif
#ifndef WIND_VOLT_MAX
#define WIND_VOLT_MAX 2.00f   // Voltaje máximo (m/s ≈ SPEED_MAX)
#endif
#ifndef WIND_SPEED_MAX
#define WIND_SPEED_MAX 32.40f // Máxima velocidad nominal (m/s)
#endif
#ifndef WIND_ADC_REF_V
#define WIND_ADC_REF_V 5.00f  // Referencia ADC (UNO/Nano típicamente 5V)
#endif
#ifndef WIND_SAMPLES_AVG
#define WIND_SAMPLES_AVG 4    // Promediar varias lecturas seguidas para reducir posible ruido o errores
#endif

class WindSpeedSensor : public ISensor {
public:
  explicit WindSpeedSensor(uint8_t speed_analog_pin = WIND_SPEED_ANALOG_PIN, uint16_t sample_interval_ms = 1000)
    : speed_analog_pin_(speed_analog_pin),
      sample_interval_ms_(sample_interval_ms),
      last_sample_ms_(0),
      available_(false)
  {}

  const char* name() const override { return "WindSpeedSensor"; }
  SensorKind kind() const override { return SensorKind::WindSpeed; }

  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true;
    last_sample_ms_ = millis();
    return true;
#else
    // Configurar entrada analógica para velocidad
    pinMode(speed_analog_pin_, INPUT);
    last_sample_ms_ = millis();
    available_ = true;
    return true;
#endif
  }

  bool poll(uint32_t nowMs, TelemetryDelta& out) override {
    if (!available_) return false;
    
    // Esperar intervalo de muestreo
    if ((uint32_t)(nowMs - last_sample_ms_) < sample_interval_ms_) return false;
    
    out = TelemetryDelta{};
    
#if SENSORS_USE_MOCK
    // Mock: onda senoidal lenta para velocidad, rotación lenta para dirección
    static uint16_t phase = 0;
    phase = (phase + 1) % 360;
    
    // Velocidad: 0-10 m/s (onda senoidal)
    float speed_mps = 5.0f + 5.0f * sinf(phase * 0.0174533f);
    out.wind_speed_cmps = (uint16_t)(speed_mps * 100.0f);
    
    // Dirección: rotación lenta 0-359°
    out.wind_dir_deg = (phase % 360);
    
    last_sample_ms_ = nowMs;
#else
    // Lecturas analógicas múltiples para suavizar
    float adc_sum = 0.0f;
    for (uint8_t i=0;i<WIND_SAMPLES_AVG;i++){
      adc_sum += analogRead(speed_analog_pin_);
    }
    float adc_avg = adc_sum / WIND_SAMPLES_AVG; // 0..1023
    float v = (adc_avg / 1023.0f) * WIND_ADC_REF_V; // Voltios
    
    // Limitar voltaje al rango esperado (protege de ruido)
    if (v < WIND_VOLT_MIN) v = WIND_VOLT_MIN;
    if (v > WIND_VOLT_MAX) v = WIND_VOLT_MAX;
    
    // Mapear linealmente a velocidad (m/s)
    float speed_mps = (v - WIND_VOLT_MIN) * (WIND_SPEED_MAX / (WIND_VOLT_MAX - WIND_VOLT_MIN));
    
    // Convertir a cm/s
    out.wind_speed_cmps = (uint16_t)(speed_mps * 100.0f);
    last_sample_ms_ = nowMs;
#endif
    
    out.has_wind = true;
    out.bump_sample = true;
    return true;
  }

  bool isAvailable() const override { return available_; }
  
private:
  uint8_t  speed_analog_pin_;
  uint16_t sample_interval_ms_;
  uint32_t last_sample_ms_;
  bool     available_;
};
