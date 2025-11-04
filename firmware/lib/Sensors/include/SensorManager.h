// -----------------------------------------------------------------------------
// SensorManager.h — Orquestador de sensores y escritura en registros Modbus
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include <registersModbus.h>

class SensorManager {
public:
  SensorManager();

  // Registra un sensor (máx. capacidad fija)
  bool registerSensor(ISensor* sensor);

  // Inicializa todos los sensores registrados
  void beginAll();

  // Iteración periódica. Llama a poll() de cada sensor y vuelca telemetrías
  void pollAll(uint32_t nowMs);

  // Configuración global (por ahora vacía, reservada para futuro)

private:
  static const uint8_t MAX_SENSORS = 4;
  ISensor* sensors_[MAX_SENSORS];
  uint8_t  sensor_count_;

  void applyTelemetry(const TelemetryDelta& t);
};
