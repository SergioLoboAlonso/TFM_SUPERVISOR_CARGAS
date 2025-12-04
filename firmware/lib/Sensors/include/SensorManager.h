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
  static const uint8_t MAX_SENSORS = 4; // Capacidad máxima de sensores gestionados en un mismo dispositivo
  ISensor* sensors_[MAX_SENSORS];
  uint8_t  sensor_count_;

  void applyTelemetry(const TelemetryDelta& t);

  // RollingStats eliminadas: RAM insuficiente en Arduino UNO
  // Estadísticas se calcularán en edge layer
  uint32_t last_poll_adjust_ms_ = 0; // para ajustar el ritmo global
};
