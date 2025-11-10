// -----------------------------------------------------------------------------
// RollingStats.h — Ventana de 5 segundos (tumbling) con min/max/avg para int16
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>

class RollingStats5s {
public:
  RollingStats5s(uint32_t window_ms = 5000)
  : window_ms_(window_ms), start_ms_(0), sum_(0), count_(0), min_(0), max_(0) {}

  // Procesa una muestra; si la ventana anterior termina, devuelve true y
  // emite el snapshot (min/max/avg) de esa ventana en los parámetros de salida.
  // Inmediatamente comienza la siguiente ventana con el valor actual.
  bool onSample(uint32_t now_ms, int16_t value, int16_t& out_min, int16_t& out_max, int16_t& out_avg){
    if (start_ms_ == 0){
      // Primera muestra: inicializar ventana con el valor actual
      start_ms_ = now_ms;
      sum_ = value;
      count_ = 1;
      min_ = value;
      max_ = value;
      return false;
    }

    // ¿Ha terminado la ventana anterior?
    if ((uint32_t)(now_ms - start_ms_) >= window_ms_){
      // Emitir snapshot de la ventana cerrada
      out_min = min_;
      out_max = max_;
      out_avg = (int16_t)(sum_ / (int32_t)count_);
      // Reiniciar ventana con la muestra actual
      start_ms_ = now_ms;
      sum_ = value;
      count_ = 1;
      min_ = value;
      max_ = value;
      return true;
    }

    // Acumular en ventana actual
    sum_ += value;
    count_++;
    if (value < min_) min_ = value;
    if (value > max_) max_ = value;
    return false;
  }

private:
  uint32_t window_ms_;
  uint32_t start_ms_;
  int32_t  sum_;
  uint16_t count_;
  int16_t  min_;
  int16_t  max_;
};
