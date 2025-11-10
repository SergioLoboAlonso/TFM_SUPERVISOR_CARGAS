// -----------------------------------------------------------------------------
// SensorManager.h — Orquestador de sensores y escritura en registros Modbus
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include <registersModbus.h>
#include <RollingStats.h>

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

  // Ventanas de 5 segundos para estadísticas (solo aceleración y viento según requerimiento)
  RollingStats5s wind_stats_;
  RollingStats5s acc_x_stats_;
  RollingStats5s acc_y_stats_;
  RollingStats5s acc_z_stats_;
  uint32_t last_poll_adjust_ms_ = 0; // para ajustar el ritmo global
};
