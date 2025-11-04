// -----------------------------------------------------------------------------
// SensorManager.cpp — Implementación
// -----------------------------------------------------------------------------
#include "SensorManager.h"

SensorManager::SensorManager() : sensor_count_(0) {
  for (uint8_t i=0;i<MAX_SENSORS;i++) sensors_[i] = nullptr;
}

bool SensorManager::registerSensor(ISensor* sensor){
  if (!sensor || sensor_count_ >= MAX_SENSORS) return false;
  sensors_[sensor_count_++] = sensor;
  return true;
}

void SensorManager::beginAll(){
  for (uint8_t i=0;i<sensor_count_;i++){
    if (sensors_[i]) sensors_[i]->begin();
  }
}

void SensorManager::pollAll(uint32_t nowMs){
  for (uint8_t i=0;i<sensor_count_;i++){
    ISensor* s = sensors_[i];
    if (!s) continue;
    TelemetryDelta t;
    if (s->poll(nowMs, t)){
      applyTelemetry(t);
    }
  }
}

void SensorManager::applyTelemetry(const TelemetryDelta& t){
  // Vuelca campos presentes a los registros Modbus
  if (t.has_accel){
    regs_set_acc_mg(t.acc_x_mg, t.acc_y_mg, t.acc_z_mg);
  }
  if (t.has_gyro){
    regs_set_gyr_mdps(t.gyr_x_mdps, t.gyr_y_mdps, t.gyr_z_mdps);
  }
  if (t.has_angles){
    regs_set_angles_mdeg(t.pitch_mdeg, t.roll_mdeg);
  }
  if (t.has_temp){
    regs_set_temp_mc(t.temp_mc);
  }
  if (t.has_load){
    // Convertir gramos a centi‑kg (1 ckg = 10 g)
    int16_t kg_load = (int16_t)(t.load_g / 10);
    regs_set_kg_load(kg_load);
  }
  if (t.bump_sample){
    regs_bump_sample_counter();
  }
}
