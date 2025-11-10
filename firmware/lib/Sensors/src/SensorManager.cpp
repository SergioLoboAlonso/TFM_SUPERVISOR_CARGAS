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
  // Control global de cadencia de muestreo desde Holding Register
  uint16_t interval_ms = regs_get_cfg_poll_interval_ms();
  if (interval_ms < 10) interval_ms = 10;
  if ((uint32_t)(nowMs - last_poll_adjust_ms_) < interval_ms) return;
  last_poll_adjust_ms_ = nowMs;

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
    // Ventana 5 s: publicar min/max/avg al rotar la ventana
    int16_t x_min, x_max, x_avg;
    int16_t y_min, y_max, y_avg;
    int16_t z_min, z_max, z_avg;
    bool rot_x = acc_x_stats_.onSample(millis(), t.acc_x_mg, x_min, x_max, x_avg);
    bool rot_y = acc_y_stats_.onSample(millis(), t.acc_y_mg, y_min, y_max, y_avg);
    bool rot_z = acc_z_stats_.onSample(millis(), t.acc_z_mg, z_min, z_max, z_avg);
    if (rot_x || rot_y || rot_z){
      // Asumimos que rotan a la vez porque comparten inicio y now; si no, igualmente publicamos la ventana que cerró
      regs_set_accel_stats(
        x_max, x_min, x_avg,
        y_max, y_min, y_avg,
        z_max, z_min, z_avg
      );
    }
  }
  if (t.has_gyro){
    regs_set_gyr_mdps(t.gyr_x_mdps, t.gyr_y_mdps, t.gyr_z_mdps);
    // Actualizar ventanas y estadísticas de giroscopio
#if STATS_FEATURE_ENABLED
    gyr_x_w_.update(t.gyr_x_mdps);
    gyr_y_w_.update(t.gyr_y_mdps);
    gyr_z_w_.update(t.gyr_z_mdps);
    regs_set_gyro_stats(
      gyr_x_w_.getMax(), gyr_x_w_.getMin(), gyr_x_w_.getAvg(),
      gyr_y_w_.getMax(), gyr_y_w_.getMin(), gyr_y_w_.getAvg(),
      gyr_z_w_.getMax(), gyr_z_w_.getMin(), gyr_z_w_.getAvg()
    );
#endif
  }
  if (t.has_angles){
    regs_set_angles_mdeg(t.pitch_mdeg, t.roll_mdeg);
  }
  if (t.has_temp){
    regs_set_temp_mc(t.temp_mc);
    // Actualizar ventana y estadísticas de temperatura
#if STATS_FEATURE_ENABLED
    temp_w_.update(t.temp_mc);
    regs_set_temp_stats(temp_w_.getMax(), temp_w_.getMin(), temp_w_.getAvg());
#endif
  }
  if (t.has_load){
    // Convertir gramos a centi‑kg (1 ckg = 10 g)
    int16_t kg_load = (int16_t)(t.load_g / 10);
    regs_set_kg_load(kg_load);
    // Actualizar ventana y estadísticas de carga (usar la misma unidad que en registros: kg*100)
#if STATS_FEATURE_ENABLED
    load_w_.update(kg_load);
    regs_set_load_stats(load_w_.getMax(), load_w_.getMin(), load_w_.getAvg());
#endif
  }
  if (t.has_wind){
    // Velocidad viento cm/s y dirección grados 0-359 (ya validados por el sensor)
    regs_set_wind(t.wind_speed_cmps, t.wind_dir_deg);
    // Ventana 5 s viento: publicar min/max/avg cuando se cierra ventana
    int16_t w_min, w_max, w_avg;
    if (wind_stats_.onSample(millis(), (int16_t)t.wind_speed_cmps, w_min, w_max, w_avg)){
      if (w_min < 0) w_min = 0; // asegurar no-negativo para cm/s
      if (w_max < 0) w_max = 0;
      if (w_avg < 0) w_avg = 0;
      regs_set_wind_stats((uint16_t)w_min, (uint16_t)w_max, (uint16_t)w_avg);
    }
  }
  if (t.bump_sample){
    regs_bump_sample_counter();
  }
}
 
