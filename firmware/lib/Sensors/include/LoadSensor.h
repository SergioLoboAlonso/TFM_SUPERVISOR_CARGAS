// -----------------------------------------------------------------------------
// LoadSensor.h — Sensor de carga/peso con HX711 (celda de carga)
// Mide peso/carga en gramos (g) con celda de carga y amplificador HX711.
// Requiere librería HX711 (https://github.com/bogde/HX711)
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

// Factor de calibración por defecto (ajustar según celda de carga)
// Típico: ~400-450 para celdas de 1-5kg; obtener con calibración manual
#ifndef HX711_CALIBRATION_FACTOR
#define HX711_CALIBRATION_FACTOR 420.0f
#endif

// Control de tara/offset por flags de compilación (PlatformIO)
// DESARROLLO (HX711_DEV_MODE=1):
//   - Ejecuta tare() en arranque (sin peso en celda)
//   - Imprime valor raw y peso cada lectura para calibración manual
//   - Permite ajuste interactivo del factor de calibración por Serial
// PRODUCCIÓN (HX711_DEV_MODE=0, default):
//   - Usa HX711_OFFSET (long) pre-capturado en desarrollo
//   - Usa HX711_CALIBRATION_FACTOR pre-calibrado
//   - Sin tara en arranque, sin prints de debug
#ifndef HX711_DEV_MODE
#define HX711_DEV_MODE 0
#endif

// Lectura crítica protegida contra interrupciones para estabilizar el timing del HX711
inline long hx711_read_critical(HX711 &scale) {
  // Esperar disponibilidad con pequeños descansos (fuera de ISR)
  uint16_t spins = 0;
  while (!scale.is_ready() && spins < 200) { delay(1); spins++; }
  if (!scale.is_ready()) return -1;
  // Desactivar interrupciones para proteger la secuencia de 24 pulsos SCK
  noInterrupts();
  delayMicroseconds(50); // breve asentamiento
  long v = scale.read();
  interrupts();
  return v;
}

class LoadSensor : public ISensor {
public:
  explicit LoadSensor(uint8_t dout_pin = HX711_DOUT_PIN, 
                      uint8_t sck_pin = HX711_SCK_PIN,
                      uint16_t sample_interval_ms = 200)
  : sample_interval_ms_(sample_interval_ms < 100 ? 100 : sample_interval_ms)
#if !SENSORS_USE_MOCK
      , scale_()
#endif
  {
#if !SENSORS_USE_MOCK
    dout_pin_ = dout_pin;
    sck_pin_ = sck_pin;
#else
    (void)dout_pin; (void)sck_pin; // Evitar warnings
#endif
  }

  const char* name() const override { return "LoadSensor"; }
  SensorKind kind() const override { return SensorKind::Load; }

  bool begin() override {
#if SENSORS_USE_MOCK
    available_ = true;
    last_ms_ = millis();
    return true;
#else
    scale_.begin(dout_pin_, sck_pin_);
    
    #if HX711_DEV_MODE
      Serial.println(F("=== HX711 MODO DESARROLLO ==="));
      Serial.println(F("Inicializando..."));
    #endif
    
    if (!scale_.is_ready()) {
      #if HX711_DEV_MODE
        Serial.println(F("ERROR: HX711 no responde"));
      #endif
      available_ = false;
      return false;
    }
    
    scale_.set_gain(128);
    scale_.set_scale(HX711_CALIBRATION_FACTOR);
    
    #if HX711_DEV_MODE
      // DESARROLLO: Tara en arranque + calibración interactiva
      Serial.println(F("Asegúrate de que NO hay peso en la celda"));
      Serial.println(F("Esperando 3 segundos..."));
      delay(3000);
      
      Serial.println(F("Ejecutando tara..."));
      scale_.power_up();
      delay(500);
      scale_.set_offset(0);
      scale_.tare(10);
      
      long zero_offset = scale_.get_offset();
      Serial.print(F("Offset capturado: "));
      Serial.println(zero_offset);
      Serial.println(F("(Guarda este valor como HX711_OFFSET para producción)"));
      Serial.println();
      Serial.println(F("=== CALIBRACIÓN ==="));
      Serial.println(F("1. Coloca un peso conocido en la celda"));
      Serial.println(F("2. Observa el valor 'Peso (g)' en las lecturas"));
      Serial.println(F("3. Ajusta HX711_CALIBRATION_FACTOR hasta que coincida"));
      Serial.print(F("Factor actual: "));
      Serial.println(HX711_CALIBRATION_FACTOR);
      Serial.println();
    #else
      // PRODUCCIÓN: Offset pre-configurado, sin tara
      #ifdef HX711_OFFSET
        scale_.set_offset((long)HX711_OFFSET);
      #else
        // Si no hay offset definido, hacer tara única en primer arranque
        scale_.power_up();
        delay(500);
        scale_.tare(10);
      #endif
    #endif
    
    available_ = true;
    last_ms_ = millis();
    return true;
#endif
  }

  bool poll(uint32_t nowMs, TelemetryDelta& out) override {
    if (!available_) return false;
    if ((uint32_t)(nowMs - last_ms_) < 100) return false;
    out = TelemetryDelta{};
#if SENSORS_USE_MOCK
    // Simular peso variable entre 0 y 5 kg con ruido
    static int16_t phase = 0; 
    phase = (phase + 7) % 360;
    float weight_kg = 2.5f + 2.0f * sinf(phase * 0.0174533f) + (random(-50, 50) / 100.0f);
    out.load_g = (int16_t)(weight_kg * 1000.0f);
    last_ms_ = nowMs;
#else
    long raw = hx711_read_critical(scale_);
    if (raw == -1) {
      #if HX711_DEV_MODE
        Serial.println(F("[HX711] ERROR: Lectura -1 (no data)"));
      #endif
      return false;
    }
    
    float weight_grams = scale_.get_units(1);
    
    #if HX711_DEV_MODE
      // Imprimir valores para calibración
      Serial.print(F("[HX711] RAW="));
      Serial.print(raw);
      Serial.print(F(" | Peso (g)="));
      Serial.println(weight_grams, 2);
    #endif
    
    if (weight_grams < -32000.0f || weight_grams > 32000.0f) {
      #if HX711_DEV_MODE
        Serial.println(F("[HX711] ERROR: Fuera de rango"));
      #endif
      return false;
    }
    
    out.load_g = (int16_t)weight_grams;
    last_ms_ = nowMs;
#endif
    out.has_load = true;
    out.bump_sample = true;
    return true;
  }  bool isAvailable() const override { return available_; }

#if !SENSORS_USE_MOCK
  // Métodos de utilidad para calibración y control
  
  // Hacer tara (establecer cero actual como referencia)
  void tare(uint8_t times = 10) {
    if (available_) {
      scale_.tare(times);
    }
  }
  
  // Ajustar factor de calibración
  void setCalibrationFactor(float factor) {
    calibration_factor_ = factor;
    scale_.set_scale(factor);
  }
  
  float getCalibrationFactor() const {
    return calibration_factor_;
  }
  
  // Leer peso raw (sin escalar) para calibración
  long readRaw() {
    return scale_.read();
  }
  
  // Obtener peso en gramos directamente
  float getWeightGrams(uint8_t times = 1) {
    return scale_.get_units(times);
  }
#endif

private:
  uint16_t sample_interval_ms_;
  uint32_t last_ms_ = 0;
  bool available_ = false;
  
#if !SENSORS_USE_MOCK
  HX711 scale_;
  uint8_t dout_pin_;
  uint8_t sck_pin_;
  float calibration_factor_ = HX711_CALIBRATION_FACTOR;
#endif
};
