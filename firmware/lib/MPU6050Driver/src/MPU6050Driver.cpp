// -----------------------------------------------------------------------------
// MPU6050Driver.cpp — Implementación del driver I²C para MPU-6050
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
//
// Referencias
// - MPU-6000 and MPU-6050 Register Map and Descriptions (Rev. 4.2)
// - InvenSense MPU-6050 
// -----------------------------------------------------------------------------

#include "MPU6050Driver.h"

// -----------------------------
// Constructor
// -----------------------------
MPU6050Driver::MPU6050Driver(uint8_t addr)
  : addr_(addr),
    accel_range_(ACCEL_RANGE_2G),
    gyro_range_(GYRO_RANGE_250DPS),
    calibrated_(false)
{
  // Inicializar offsets a cero
  for (int i = 0; i < 3; i++) {
    accel_offset_[i] = 0;
    gyro_offset_[i] = 0;
  }
}

// -----------------------------
// Inicialización
// -----------------------------
bool MPU6050Driver::begin() {
  // Inicializar Wire (I²C)
  Wire.begin();
  Wire.setClock(400000UL);  // 400 kHz (Fast Mode)
  
  // CRÍTICO: Configurar timeout I²C para evitar bloqueos si el sensor no responde
  Wire.setWireTimeout(25000, true);  // 25ms timeout, reset on timeout
  
  delay(100);  // Esperar más tiempo a que el MPU-6050 se estabilice después del power-up
  
  // Salir de sleep mode (PWR_MGMT_1 = 0x00)
  // Bit 6 (SLEEP) = 0, Bit 5 (CYCLE) = 0, resto = 0 (reloj interno 8MHz)
  if (!writeRegister(MPU6050_REG_PWR_MGMT_1, 0x00)) {
    return false;  // Fallo en comunicación I²C
  }
  
  delay(100);  // Esperar a que el chip salga de sleep y se estabilice
  
  // Verificar WHO_AM_I (debe ser 0x68)
  if (!isConnected()) {
    return false;
  }
  
  // Configuración por defecto
  setAccelRange(ACCEL_RANGE_2G);       // ±2g
  setGyroRange(GYRO_RANGE_250DPS);     // ±250°/s
  setDLPF(3);                          // 42 Hz (buen compromiso)
  
  // Sample Rate = Gyroscope Output Rate / (1 + SMPLRT_DIV)
  // Con DLPF habilitado (mode != 0), Gyro Output Rate = 1 kHz
  // SMPLRT_DIV = 9 → Sample Rate = 1000 / (1+9) = 100 Hz
  writeRegister(MPU6050_REG_SMPLRT_DIV, 9);
  
  return true;
}

// -----------------------------
// Verificación de conectividad
// -----------------------------
bool MPU6050Driver::isConnected() {
  uint8_t whoami = 0;
  if (!readRegister(MPU6050_REG_WHO_AM_I, whoami)) {
    return false;
  }
  return (whoami == MPU6050_WHO_AM_I_VAL);
}

// -----------------------------
// Lecturas RAW
// -----------------------------
bool MPU6050Driver::readRawAccel(int16_t& x, int16_t& y, int16_t& z) {
  uint8_t buffer[6];
  if (!readRegisters(MPU6050_REG_ACCEL_XOUT_H, buffer, 6)) {
    return false;
  }
  
  // Big-endian: MSB primero
  x = (int16_t)((buffer[0] << 8) | buffer[1]);
  y = (int16_t)((buffer[2] << 8) | buffer[3]);
  z = (int16_t)((buffer[4] << 8) | buffer[5]);
  
  return true;
}

bool MPU6050Driver::readRawGyro(int16_t& x, int16_t& y, int16_t& z) {
  uint8_t buffer[6];
  if (!readRegisters(MPU6050_REG_GYRO_XOUT_H, buffer, 6)) {
    return false;
  }
  
  // Big-endian: MSB primero
  x = (int16_t)((buffer[0] << 8) | buffer[1]);
  y = (int16_t)((buffer[2] << 8) | buffer[3]);
  z = (int16_t)((buffer[4] << 8) | buffer[5]);
  
  return true;
}

bool MPU6050Driver::readRawTemp(int16_t& temp) {
  uint8_t buffer[2];
  if (!readRegisters(MPU6050_REG_TEMP_OUT_H, buffer, 2)) {
    return false;
  }
  
  // Big-endian: MSB primero
  temp = (int16_t)((buffer[0] << 8) | buffer[1]);
  
  return true;
}

// -----------------------------
// Lecturas ESCALADAS
// -----------------------------
bool MPU6050Driver::readAccelMg(int16_t& x, int16_t& y, int16_t& z) {
  int16_t raw_x, raw_y, raw_z;
  
  if (!readRawAccel(raw_x, raw_y, raw_z)) {
    return false;
  }
  
  // Obtener factor de escala (mg por LSB)
  float scale = getAccelScaleFactor();
  
  // Convertir a mg (mili-g) y aplicar offsets si están calibrados
  x = (int16_t)((raw_x - accel_offset_[0]) * scale);
  y = (int16_t)((raw_y - accel_offset_[1]) * scale);
  z = (int16_t)((raw_z - accel_offset_[2]) * scale);
  
  return true;
}

bool MPU6050Driver::readGyroMdps(int16_t& x, int16_t& y, int16_t& z) {
  int16_t raw_x, raw_y, raw_z;
  
  if (!readRawGyro(raw_x, raw_y, raw_z)) {
    return false;
  }
  
  // Obtener factor de escala (mdps por LSB)
  float scale = getGyroScaleFactor();
  
  // Convertir a mdps (mili-grados por segundo) y aplicar offsets
  x = (int16_t)((raw_x - gyro_offset_[0]) * scale);
  y = (int16_t)((raw_y - gyro_offset_[1]) * scale);
  z = (int16_t)((raw_z - gyro_offset_[2]) * scale);
  
  return true;
}

int16_t MPU6050Driver::readTempCenti() {
  int16_t raw_temp;
  
  if (!readRawTemp(raw_temp)) {
    return 0;  // Retornar 0 en caso de error
  }
  
  // Fórmula de conversión del datasheet:
  // Temperature in degrees C = (TEMP_OUT Register Value as a signed quantity)/340 + 36.53
  // Escalamos a centésimas: temp_mc = temp_c * 100
  
  // Cálculo: temp_c = (raw / 340.0) + 36.53
  // temp_mc = (raw * 100 / 340.0) + 3653
  // temp_mc ≈ (raw * 10 / 34) + 3653
  
  // Usamos float para precisión
  float temp_c = (raw_temp / 340.0f) + 36.53f;
  int16_t temp_mc = (int16_t)(temp_c * 100.0f);
  
  return temp_mc;
}

// -----------------------------
// Configuración
// -----------------------------
void MPU6050Driver::setAccelRange(AccelRange range) {
  accel_range_ = range;
  
  // ACCEL_CONFIG: bits 4:3 = AFS_SEL (rango acelerómetro)
  // 00 = ±2g, 01 = ±4g, 10 = ±8g, 11 = ±16g
  uint8_t config = (uint8_t)(range << 3);
  writeRegister(MPU6050_REG_ACCEL_CONFIG, config);
}

void MPU6050Driver::setGyroRange(GyroRange range) {
  gyro_range_ = range;
  
  // GYRO_CONFIG: bits 4:3 = FS_SEL (rango giroscopio)
  // 00 = ±250°/s, 01 = ±500°/s, 10 = ±1000°/s, 11 = ±2000°/s
  uint8_t config = (uint8_t)(range << 3);
  writeRegister(MPU6050_REG_GYRO_CONFIG, config);
}

void MPU6050Driver::setDLPF(uint8_t mode) {
  // CONFIG: bits 2:0 = DLPF_CFG
  // Limitar a 0-6 (valores válidos según datasheet)
  if (mode > 6) {
    mode = 6;
  }
  
  writeRegister(MPU6050_REG_CONFIG, mode);
}

// -----------------------------
// Calibración (placeholder)
// -----------------------------
void MPU6050Driver::calibrate(uint16_t samples) {
  // TODO: Implementar calibración automática
  // Algoritmo básico:
  // 1. Leer 'samples' muestras raw de accel/gyro
  // 2. Promediar para obtener offsets
  // 3. Para accel: asumir Z ≈ +1g (gravedad), X e Y ≈ 0
  // 4. Para gyro: asumir todos ≈ 0 (sensor inmóvil)
  // 5. Almacenar en accel_offset_[] y gyro_offset_[]
  // 6. Marcar calibrated_ = true
  
  // Por ahora, solo reset de offsets
  for (int i = 0; i < 3; i++) {
    accel_offset_[i] = 0;
    gyro_offset_[i] = 0;
  }
  calibrated_ = false;
  
  // Placeholder para futuras mejoras:
  // int32_t sum_ax = 0, sum_ay = 0, sum_az = 0;
  // int32_t sum_gx = 0, sum_gy = 0, sum_gz = 0;
  // 
  // for (uint16_t i = 0; i < samples; i++) {
  //   int16_t ax, ay, az, gx, gy, gz;
  //   readRawAccel(ax, ay, az);
  //   readRawGyro(gx, gy, gz);
  //   sum_ax += ax; sum_ay += ay; sum_az += az;
  //   sum_gx += gx; sum_gy += gy; sum_gz += gz;
  //   delay(10);
  // }
  // 
  // accel_offset_[0] = sum_ax / samples;
  // accel_offset_[1] = sum_ay / samples;
  // accel_offset_[2] = (sum_az / samples) - 16384;  // Compensar gravedad (±2g)
  // gyro_offset_[0] = sum_gx / samples;
  // gyro_offset_[1] = sum_gy / samples;
  // gyro_offset_[2] = sum_gz / samples;
  // calibrated_ = true;
}

// -----------------------------
// Métodos privados I²C
// -----------------------------
bool MPU6050Driver::readRegister(uint8_t reg, uint8_t& value) {
  Wire.beginTransmission(addr_);
  Wire.write(reg);
  
  if (Wire.endTransmission(false) != 0) {  // Repeated start
    return false;
  }
  
  Wire.requestFrom(addr_, (uint8_t)1);
  if (Wire.available() != 1) {
    return false;
  }
  
  value = Wire.read();
  return true;
}

bool MPU6050Driver::writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr_);
  Wire.write(reg);
  Wire.write(value);
  
  return (Wire.endTransmission() == 0);
}

bool MPU6050Driver::readRegisters(uint8_t reg, uint8_t* buffer, uint8_t length) {
  Wire.beginTransmission(addr_);
  Wire.write(reg);
  
  if (Wire.endTransmission(false) != 0) {  // Repeated start
    return false;
  }
  
  Wire.requestFrom(addr_, length);
  
  uint8_t count = 0;
  while (Wire.available() && count < length) {
    buffer[count++] = Wire.read();
  }
  
  return (count == length);
}

// -----------------------------
// Factores de escala
// -----------------------------
float MPU6050Driver::getAccelScaleFactor() const {
  // Sensibilidades según datasheet (LSB/g):
  // ±2g  → 16384 LSB/g → 1000 mg / 16384 LSB = 0.06103515625 mg/LSB
  // ±4g  → 8192 LSB/g  → 1000 mg / 8192 LSB  = 0.1220703125 mg/LSB
  // ±8g  → 4096 LSB/g  → 1000 mg / 4096 LSB  = 0.244140625 mg/LSB
  // ±16g → 2048 LSB/g  → 1000 mg / 2048 LSB  = 0.48828125 mg/LSB
  
  switch (accel_range_) {
    case ACCEL_RANGE_2G:  return 1000.0f / 16384.0f;  // 0.061 mg/LSB
    case ACCEL_RANGE_4G:  return 1000.0f / 8192.0f;   // 0.122 mg/LSB
    case ACCEL_RANGE_8G:  return 1000.0f / 4096.0f;   // 0.244 mg/LSB
    case ACCEL_RANGE_16G: return 1000.0f / 2048.0f;   // 0.488 mg/LSB
    default:              return 1000.0f / 16384.0f;  // Default ±2g
  }
}

float MPU6050Driver::getGyroScaleFactor() const {
  // Sensibilidades según datasheet (LSB/(°/s)):
  // ±250°/s  → 131 LSB/(°/s)   → 1000 mdps / 131 LSB    = 7.633 mdps/LSB
  // ±500°/s  → 65.5 LSB/(°/s)  → 1000 mdps / 65.5 LSB   = 15.267 mdps/LSB
  // ±1000°/s → 32.8 LSB/(°/s)  → 1000 mdps / 32.8 LSB   = 30.488 mdps/LSB
  // ±2000°/s → 16.4 LSB/(°/s)  → 1000 mdps / 16.4 LSB   = 60.976 mdps/LSB
  
  switch (gyro_range_) {
    case GYRO_RANGE_250DPS:  return 1000.0f / 131.0f;   // 7.633 mdps/LSB
    case GYRO_RANGE_500DPS:  return 1000.0f / 65.5f;    // 15.267 mdps/LSB
    case GYRO_RANGE_1000DPS: return 1000.0f / 32.8f;    // 30.488 mdps/LSB
    case GYRO_RANGE_2000DPS: return 1000.0f / 16.4f;    // 60.976 mdps/LSB
    default:                 return 1000.0f / 131.0f;   // Default ±250°/s
  }
}
