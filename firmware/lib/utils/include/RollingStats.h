// -----------------------------------------------------------------------------
// RollingStats.h — Ventana de 5 segundos (tumbling) con min/max/avg para int16
// OPTIMIZADO: usa uint32_t para timestamps (correcto) pero elimina sum_ (calcula avg incremental)
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>

class RollingStats5s {
public:
  RollingStats5s(uint16_t window_ms = 5000)
  : window_ms_(window_ms), start_ms_(0), avg_(0), count_(0), min_(0), max_(0) {}

  // Procesa una muestra; si la ventana anterior termina, devuelve true y
  // emite el snapshot (min/max/avg) de esa ventana en los parámetros de salida.
  // Inmediatamente comienza la siguiente ventana con el valor actual.
  bool onSample(uint32_t now_ms, int16_t value, int16_t& out_min, int16_t& out_max, int16_t& out_avg){
    if (start_ms_ == 0){
      // Primera muestra: inicializar ventana con el valor actual
      start_ms_ = now_ms;
      avg_ = value;
      count_ = 1;
      min_ = value;
      max_ = value;
      return false;
    }

    // ¿Ha terminado la ventana anterior?
    if ((now_ms - start_ms_) >= window_ms_){
      // Emitir snapshot de la ventana cerrada
      out_min = min_;
      out_max = max_;
      out_avg = avg_;
      // Reiniciar ventana con la muestra actual
      start_ms_ = now_ms;
      avg_ = value;
      count_ = 1;
      min_ = value;
      max_ = value;
      return true;
    }

    // Acumular en ventana actual usando promedio incremental
    // nueva_media = ((media_anterior × N) + nuevo_valor) / (N+1)
    // Pero para evitar overflow con int32, usar: nueva_media = media + (valor - media) / (N+1)
    count_++;
    avg_ = avg_ + (int16_t)((value - avg_) / (int16_t)count_);
    
    if (value < min_) min_ = value;
    if (value > max_) max_ = value;
    return false;
  }

  // Getters para obtener stats acumulados de la ventana actual
  int16_t getMin() const { return min_; }
  int16_t getMax() const { return max_; }
  int16_t getAvg() const { return avg_; }

private:
  uint16_t window_ms_;  // 2 bytes
  uint32_t start_ms_;   // 4 bytes (correcto para millis())
  int16_t  avg_;        // 2 bytes (promedio incremental, antes sum_=4 bytes) ✂️ -2 bytes
  uint16_t count_;      // 2 bytes
  int16_t  min_;        // 2 bytes
  int16_t  max_;        // 2 bytes
  // TOTAL: 14 bytes por instancia
  // 4 instancias: 56 bytes
};
