// -----------------------------------------------------------------------------
// AccelerometerSensor.h — Sensor de acelerómetro genérico (stub / mock)
// Entrega aceleraciones en mg.
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include "SensorConfig.h"

class AccelerometerSensor : public ISensor {
public:
  explicit AccelerometerSensor(uint16_t sample_interval_ms = 100)
    : sample_interval_ms_(sample_interval_ms) {}

  const char* name() const override { return "AccelerometerSensor"; }
  SensorKind kind() const override { return SensorKind::Accelerometer; }

  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true;
    last_ms_ = millis();
    return true;
#else
    available_ = false; // TODO: inicializar HW real
    return false;
#endif
  }

  bool poll(uint32_t nowMs, TelemetryDelta& out) override {
    if (!available_) return false;
    if ((uint32_t)(nowMs - last_ms_) < sample_interval_ms_) return false;
    last_ms_ = nowMs;
    out = TelemetryDelta{};
#if SENSORS_USE_MOCK
    // Trayectorias senoidales suaves en mg
    static int16_t phase = 0; phase = (phase + 5) % 360;
    out.acc_x_mg = (int16_t)(1000.0f * sinf(phase * 0.0174533f));
    out.acc_y_mg = (int16_t)(500.0f * cosf(phase * 0.0174533f));
    out.acc_z_mg = 1000; // ~1g
    out.has_accel = true;
#endif
    out.bump_sample = true;
    return true;
  }

  bool isAvailable() const override { return available_; }

private:
  uint16_t sample_interval_ms_ = 100;
  uint32_t last_ms_ = 0;
  bool available_ = false;
};
