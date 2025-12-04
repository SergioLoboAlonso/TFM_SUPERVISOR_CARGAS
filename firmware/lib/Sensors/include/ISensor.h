// -----------------------------------------------------------------------------
// ISensor.h — Interfaz base para sensores
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "SensorTypes.h"

class ISensor {
public:
  virtual ~ISensor() {}

  // Nombre descriptivo (para logs o diagnóstico)
  virtual const char* name() const = 0;

  // Tipo de sensor (opcional)
  virtual SensorKind kind() const { return SensorKind::Unknown; }

  // Inicialización del sensor; devuelve true si operativo
  virtual bool begin() = 0;

  // Poll no bloqueante. nowMs = millis()
  // Debe rellenar 'out' cuando haya nueva telemetría disponible y devolver true.
  // Si no hay nuevos datos, devolver false.
  virtual bool poll(uint32_t nowMs, TelemetryDelta& out) = 0;

  // Señala si el sensor está disponible/operativo
  virtual bool isAvailable() const = 0;
};
