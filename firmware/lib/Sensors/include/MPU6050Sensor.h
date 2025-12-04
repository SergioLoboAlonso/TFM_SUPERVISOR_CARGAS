// -----------------------------------------------------------------------------
// MPU6050Sensor.h — Adaptador ISensor para MPU-6050 (acelerómetro/giroscopio)
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include "ISensor.h"
#include <MPU6050Driver.h>
#include <AngleCalculator.h>
#include "config_pins.h"

class MPU6050Sensor : public ISensor {
public:
  explicit MPU6050Sensor(uint8_t i2c_addr = MPU6050_I2C_ADDR,
                         uint16_t sample_interval_ms = 100)
    : addr_(i2c_addr), sample_interval_ms_(sample_interval_ms) {}

  const char* name() const override { return "MPU6050Sensor"; }
  SensorKind kind() const override { return SensorKind::InclinometerIMU; }

  bool begin() override {
    // Intentar inicializar hasta 3 veces con delays incrementales
    for (uint8_t retry = 0; retry < 3; retry++) {
      if (retry > 0) {
        delay(100 * retry);  // 100ms, 200ms
      }
      
      if (mpu_.begin()) {
        // Config por defecto
        mpu_.setAccelRange(ACCEL_RANGE_2G);
        mpu_.setGyroRange(GYRO_RANGE_250DPS);
        mpu_.setDLPF(3);               // ~42 Hz
        angles_.setFilterAlpha(0.3f);  // suavizado moderado
        available_ = true;
        last_ms_ = millis();
        return true;
      }
    }
    
    // Si falló después de 3 intentos
    available_ = false;
    return false;
  }

  bool poll(uint32_t nowMs, TelemetryDelta& out) override {
    // Si no está disponible, intentar reinicializar cada 5 segundos
    if (!available_) {
      static uint32_t last_retry = 0;
      if ((nowMs - last_retry) > 5000) {
        last_retry = nowMs;
        if (mpu_.begin()) {
          mpu_.setAccelRange(ACCEL_RANGE_2G);
          mpu_.setGyroRange(GYRO_RANGE_250DPS);
          mpu_.setDLPF(3);
          available_ = true;
        }
      }
      return false;
    }
    
    if ((uint32_t)(nowMs - last_ms_) < sample_interval_ms_) return false;
    last_ms_ = nowMs;

    int16_t ax, ay, az;
    int16_t gx, gy, gz;
    out = TelemetryDelta{};

    // Acelerómetro y ángulos
    bool accel_ok = mpu_.readAccelMg(ax, ay, az);
    if (accel_ok) {
      out.has_accel = true;
      out.acc_x_mg = ax; out.acc_y_mg = ay; out.acc_z_mg = az;
      angles_.update(ax, ay, az);
      out.has_angles = true;
      out.pitch_mdeg = angles_.getPitchMdeg();
      out.roll_mdeg  = angles_.getRollMdeg();
    }

    // Giroscopio
    bool gyro_ok = mpu_.readGyroMdps(gx, gy, gz);
    if (gyro_ok) {
      out.has_gyro = true;
      out.gyr_x_mdps = gx; out.gyr_y_mdps = gy; out.gyr_z_mdps = gz;
    }

    // Temperatura
    int16_t temp = mpu_.readTempCenti();
    if (temp != 0) {  // Si devuelve 0 probablemente falló
      out.temp_mc = temp;
      out.has_temp = true;
    }

    // Si TODAS las lecturas fallaron, marcar sensor como no disponible
    if (!accel_ok && !gyro_ok && temp == 0) {
      available_ = false;
      return false;
    }

    out.bump_sample = true; // nueva muestra completa
    return true;
  }

  bool isAvailable() const override { return available_; }

  // Permitir ajuste de DLPF aproximando por frecuencia (Hz)
  void setDLPF_Hz(uint16_t hz){
    // Mapeo simple por umbrales a los modos 0..6
    // 0:~260,1:184,2:94,3:44,4:21,5:10,6:5
    uint8_t mode = 3;
    if (hz >= 200) mode = 0;
    else if (hz >= 150) mode = 1;
    else if (hz >= 70)  mode = 2;
    else if (hz >= 30)  mode = 3;
    else if (hz >= 15)  mode = 4;
    else if (hz >= 8)   mode = 5;
    else                mode = 6;
    mpu_.setDLPF(mode);
  }

private:
  uint8_t addr_;
  uint16_t sample_interval_ms_;
  uint32_t last_ms_ = 0;
  bool available_ = false;

  MPU6050Driver mpu_{addr_};
  AngleCalculator angles_{};
};
