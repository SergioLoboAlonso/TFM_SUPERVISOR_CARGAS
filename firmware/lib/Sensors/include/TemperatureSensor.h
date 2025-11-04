// -----------------------------------------------------------------------------
// TemperatureSensor.h — Sensor de temperatura DS18B20 (OneWire)
// Implementa ISensor y entrega temperatura en mc (centésimas de grado Celsius).
// Requiere librería OneWire y DallasTemperature.
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include "SensorConfig.h"

#if !SENSORS_USE_MOCK
#include <OneWire.h>
#include <DallasTemperature.h>
#endif

// Pin por defecto para DS18B20; puede sobreescribirse desde platformio.ini
#ifndef DS18B20_PIN
#define DS18B20_PIN 7
#endif

class TemperatureSensor : public ISensor {
public:
  explicit TemperatureSensor(uint8_t one_wire_pin = DS18B20_PIN, 
                              uint16_t sample_interval_ms = 500)
    : sample_interval_ms_(sample_interval_ms)
#if !SENSORS_USE_MOCK
      , one_wire_(one_wire_pin)
      , dallas_(&one_wire_)
#endif
  {
    (void)one_wire_pin; // Evitar warning si MOCK
  }

  const char* name() const override { return "TemperatureSensor"; }
  SensorKind kind() const override { return SensorKind::Temperature; }

  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true;
    last_ms_ = millis();
    return true;
#else
    dallas_.begin();
    device_count_ = dallas_.getDeviceCount();
    
    if (device_count_ == 0) {
      available_ = false;
      return false;
    }
    
    // Obtener dirección del primer dispositivo
    if (!dallas_.getAddress(device_address_, 0)) {
      available_ = false;
      return false;
    }
    
    // Configurar resolución (9-12 bits; 12=máxima precisión, 750ms conversión)
    dallas_.setResolution(device_address_, 12);
    
    // Solicitar primera lectura
    dallas_.requestTemperatures();
    conversion_requested_ms_ = millis();
    
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
    // Onda lenta entre 20.00°C y 25.00°C
    static int16_t phase = 0; 
    phase = (phase + 1) % 200;
    int16_t temp_mc = 2000 + (int16_t)(500.0f * sinf(phase * 0.0314159f));
    out.temp_mc = temp_mc;
    last_ms_ = nowMs;
#else
    // Esperar a que conversión esté lista (DS18B20 tarda ~750ms en resolución 12-bit)
    if ((uint32_t)(nowMs - conversion_requested_ms_) < 750) {
      return false; // Conversión aún en proceso
    }
    
    // Leer temperatura
    float temp_celsius = dallas_.getTempC(device_address_);
    
    // Validar lectura (-127°C indica error de lectura)
    if (temp_celsius == DEVICE_DISCONNECTED_C || temp_celsius < -55.0f || temp_celsius > 125.0f) {
      // Sensor desconectado o lectura fuera de rango; reintentar
      dallas_.requestTemperatures();
      conversion_requested_ms_ = nowMs;
      return false;
    }
    
    // Convertir a mc (centésimas de °C)
    out.temp_mc = (int16_t)(temp_celsius * 100.0f);
    
    // Solicitar siguiente conversión
    dallas_.requestTemperatures();
    conversion_requested_ms_ = nowMs;
    last_ms_ = nowMs;
#endif
    
    out.has_temp = true;
    out.bump_sample = true;
    return true;
  }

  bool isAvailable() const override { return available_; }

#if !SENSORS_USE_MOCK
  // Métodos de utilidad para diagnóstico
  uint8_t getDeviceCount() const { return device_count_; }
  
  void getDeviceAddress(uint8_t* addr) const {
    for (uint8_t i = 0; i < 8; i++) {
      addr[i] = device_address_[i];
    }
  }
#endif

private:
  uint16_t sample_interval_ms_;
  uint32_t last_ms_ = 0;
  bool available_ = false;
  
#if !SENSORS_USE_MOCK
  OneWire one_wire_;
  DallasTemperature dallas_;
  uint8_t device_address_[8];
  uint8_t device_count_ = 0;
  uint32_t conversion_requested_ms_ = 0;
#endif
};
