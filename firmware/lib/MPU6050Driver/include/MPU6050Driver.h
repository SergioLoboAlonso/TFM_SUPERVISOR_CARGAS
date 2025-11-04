// -----------------------------------------------------------------------------
// MPU6050Driver.h — Driver I²C para sensor MPU-6050 (acelerómetro + giroscopio)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
//
// Responsabilidades
// - Inicialización y configuración del MPU-6050 vía I²C (Wire)
// - Lectura de acelerómetro (3 ejes) en valores raw y escalados a mg
// - Lectura de giroscopio (3 ejes) en valores raw y escalados a mdps
// - Lectura de temperatura en valores raw y escalados a centésimas de °C
// - Configuración de rangos (accel: ±2/4/8/16g; gyro: ±250/500/1000/2000°/s)
// - Configuración de filtro pasa-bajos digital (DLPF)
// - Detección de errores de comunicación I²C
//
// Notas de implementación
// - Usa <Wire.h> para comunicación I²C (pines A4/A5 en UNO/NANO)
// - Compatibilidad con registersModbus.h (unidades mg, mdps, mc)
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>
#include <Wire.h>
#include <stdint.h>

// -----------------------------
// Registros MPU-6050 (subset usado)
// -----------------------------
#define MPU6050_REG_PWR_MGMT_1      0x6B  // Power Management 1
#define MPU6050_REG_PWR_MGMT_2      0x6C  // Power Management 2
#define MPU6050_REG_SMPLRT_DIV      0x19  // Sample Rate Divider
#define MPU6050_REG_CONFIG          0x1A  // Configuration (DLPF)
#define MPU6050_REG_GYRO_CONFIG     0x1B  // Gyroscope Configuration
#define MPU6050_REG_ACCEL_CONFIG    0x1C  // Accelerometer Configuration
#define MPU6050_REG_ACCEL_XOUT_H    0x3B  // Accel X High Byte (inicio bloque 14B)
#define MPU6050_REG_TEMP_OUT_H      0x41  // Temperatura High Byte
#define MPU6050_REG_GYRO_XOUT_H     0x43  // Gyro X High Byte
#define MPU6050_REG_WHO_AM_I        0x75  // Identificador chip (0x68)

// Valor esperado en WHO_AM_I
#define MPU6050_WHO_AM_I_VAL        0x68

// -----------------------------
// Enumeraciones de configuración
// -----------------------------
enum AccelRange : uint8_t {
  ACCEL_RANGE_2G  = 0,  // ±2g  → sensibilidad 16384 LSB/g
  ACCEL_RANGE_4G  = 1,  // ±4g  → sensibilidad 8192 LSB/g
  ACCEL_RANGE_8G  = 2,  // ±8g  → sensibilidad 4096 LSB/g
  ACCEL_RANGE_16G = 3   // ±16g → sensibilidad 2048 LSB/g
};

enum GyroRange : uint8_t {
  GYRO_RANGE_250DPS  = 0,  // ±250°/s  → sensibilidad 131 LSB/(°/s)
  GYRO_RANGE_500DPS  = 1,  // ±500°/s  → sensibilidad 65.5 LSB/(°/s)
  GYRO_RANGE_1000DPS = 2,  // ±1000°/s → sensibilidad 32.8 LSB/(°/s)
  GYRO_RANGE_2000DPS = 3   // ±2000°/s → sensibilidad 16.4 LSB/(°/s)
};

// Modos de filtro pasa-bajos digital (DLPF)
// Valores 0-6: frecuencia de corte de ~260 Hz a ~5 Hz
// Valor 0 = 260 Hz (sin filtrado prácticamente)
// Valor 6 = 5 Hz (muy filtrado, mayor latencia)
// Recomendado: 3 (44 Hz accel, 42 Hz gyro) para aplicaciones de inclinación

// -----------------------------
// Clase MPU6050Driver
// -----------------------------
class MPU6050Driver {
public:
  /**
   * @brief Constructor del driver MPU-6050
   * 
   * @param addr Dirección I²C del MPU-6050 (0x68 si AD0=GND, 0x69 si AD0=VCC)
   */
  explicit MPU6050Driver(uint8_t addr = 0x68);

  /**
   * @brief Inicializa el sensor MPU-6050
   * 
   * Secuencia de inicialización:
   * - Inicializa Wire (I²C)
   * - Sale de sleep mode (PWR_MGMT_1 = 0x00)
   * - Verifica WHO_AM_I (debe ser 0x68)
   * - Configura rangos por defecto (±2g, ±250°/s)
   * - Configura DLPF por defecto (modo 3: 42 Hz)
   * 
   * @return true si la inicialización fue exitosa
   * @return false si falla comunicación I²C o WHO_AM_I incorrecto
   */
  bool begin();

  /**
   * @brief Verifica conectividad con el MPU-6050
   * 
   * Lee el registro WHO_AM_I y valida que sea 0x68
   * 
   * @return true si el sensor responde correctamente
   * @return false si falla la comunicación I²C
   */
  bool isConnected();

  // -----------------------------
  // Lecturas RAW (valores de 16 bits del sensor)
  // -----------------------------
  
  /**
   * @brief Lee valores raw del acelerómetro
   * 
   * @param x Referencia para almacenar aceleración raw en eje X
   * @param y Referencia para almacenar aceleración raw en eje Y
   * @param z Referencia para almacenar aceleración raw en eje Z
   * @return true si la lectura fue exitosa, false si falla I²C
   */
  bool readRawAccel(int16_t& x, int16_t& y, int16_t& z);

  /**
   * @brief Lee valores raw del giroscopio
   * 
   * @param x Referencia para almacenar velocidad angular raw en eje X
   * @param y Referencia para almacenar velocidad angular raw en eje Y
   * @param z Referencia para almacenar velocidad angular raw en eje Z
   * @return true si la lectura fue exitosa, false si falla I²C
   */
  bool readRawGyro(int16_t& x, int16_t& y, int16_t& z);

  /**
   * @brief Lee valor raw de temperatura
   * 
   * @param temp Referencia para almacenar temperatura raw
   * @return true si la lectura fue exitosa, false si falla I²C
   * 
   * @note Conversión: Temp_C = (raw / 340.0) + 36.53
   */
  bool readRawTemp(int16_t& temp);

  // -----------------------------
  // Lecturas ESCALADAS (unidades físicas compatibles con registersModbus)
  // -----------------------------
  
  /**
   * @brief Lee aceleración en mili-g (mg)
   * 
   * Escala los valores raw según el rango configurado.
   * Por ejemplo, rango ±2g → sensibilidad 16384 LSB/g → 1000 mg = 16384 LSB
   * 
   * @param x Referencia para aceleración en eje X (mg)
   * @param y Referencia para aceleración en eje Y (mg)
   * @param z Referencia para aceleración en eje Z (mg)
   * @return true si la lectura fue exitosa
   * 
   * @note Compatible con regs_set_acc_mg(x, y, z)
   */
  bool readAccelMg(int16_t& x, int16_t& y, int16_t& z);

  /**
   * @brief Lee velocidad angular en mili-grados por segundo (mdps)
   * 
   * Escala los valores raw según el rango configurado.
   * Por ejemplo, rango ±250°/s → sensibilidad 131 LSB/(°/s) → 1000 mdps = 131 LSB
   * 
   * @param x Referencia para velocidad angular en eje X (mdps)
   * @param y Referencia para velocidad angular en eje Y (mdps)
   * @param z Referencia para velocidad angular en eje Z (mdps)
   * @return true si la lectura fue exitosa
   * 
   * @note Compatible con regs_set_gyr_mdps(x, y, z)
   */
  bool readGyroMdps(int16_t& x, int16_t& y, int16_t& z);

  /**
   * @brief Lee temperatura en centésimas de °C (0.01°C)
   * 
   * Fórmula: Temp_C = (raw / 340.0) + 36.53
   * Resultado escalado a centésimas: Temp_mc = Temp_C * 100
   * 
   * @return Temperatura en centésimas de °C, o 0 si falla la lectura
   * 
   * @note Compatible con regs_set_temp_mc(temp)
   */
  int16_t readTempCenti();

  // -----------------------------
  // Configuración del sensor
  // -----------------------------
  
  /**
   * @brief Configura el rango del acelerómetro
   * 
   * @param range Rango deseado (ACCEL_RANGE_2G, 4G, 8G o 16G)
   * 
   * @note Mayor rango → menor sensibilidad pero más margen dinámico
   * @note Para detección de inclinación estática, ±2g es suficiente
   */
  void setAccelRange(AccelRange range);

  /**
   * @brief Configura el rango del giroscopio
   * 
   * @param range Rango deseado (GYRO_RANGE_250DPS, 500DPS, 1000DPS o 2000DPS)
   * 
   * @note Mayor rango → menor sensibilidad pero más margen dinámico
   * @note Para detección de vibración lenta, ±250°/s es suficiente
   */
  void setGyroRange(GyroRange range);

  /**
   * @brief Configura el filtro pasa-bajos digital (DLPF)
   * 
   * @param mode Modo DLPF (0-6):
   *   - 0: ~260 Hz (sin filtrado)
   *   - 1: 184 Hz
   *   - 2: 94 Hz
   *   - 3: 44 Hz (accel) / 42 Hz (gyro) [RECOMENDADO]
   *   - 4: 21 Hz
   *   - 5: 10 Hz
   *   - 6: 5 Hz (muy filtrado)
   * 
   * @note Menor frecuencia = más suave pero más latencia
   * @note Modo 3 (42 Hz) es buen compromiso para inclinómetro
   */
  void setDLPF(uint8_t mode);

  /**
   * @brief Obtiene el rango actual del acelerómetro
   * 
   * @return Rango configurado (AccelRange)
   */
  AccelRange getAccelRange() const { return accel_range_; }

  /**
   * @brief Obtiene el rango actual del giroscopio
   * 
   * @return Rango configurado (GyroRange)
   */
  GyroRange getGyroRange() const { return gyro_range_; }

  // -----------------------------
  // Calibración (opcional, para futuras mejoras)
  // -----------------------------
  
  /**
   * @brief Calibra offsets del sensor
   * 
   * Calcula valores medios de accel/gyro con el sensor en reposo
   * y los almacena como offsets. Útil para compensar deriva térmica.
   * 
   * @param samples Número de muestras a promediar (por defecto 100)
   * 
   * @note El sensor debe estar completamente inmóvil durante la calibración
   * @note Los offsets se aplican automáticamente en lecturas escaladas
   * @warning No implementado en versión inicial (placeholder)
   */
  void calibrate(uint16_t samples = 100);

private:
  // -----------------------------
  // Métodos privados I²C
  // -----------------------------
  
  /**
   * @brief Lee un byte de un registro
   * 
   * @param reg Dirección del registro
   * @param value Referencia para almacenar el valor leído
   * @return true si la lectura fue exitosa
   */
  bool readRegister(uint8_t reg, uint8_t& value);

  /**
   * @brief Escribe un byte en un registro
   * 
   * @param reg Dirección del registro
   * @param value Valor a escribir
   * @return true si la escritura fue exitosa
   */
  bool writeRegister(uint8_t reg, uint8_t value);

  /**
   * @brief Lee múltiples bytes consecutivos
   * 
   * @param reg Dirección del primer registro
   * @param buffer Buffer de salida
   * @param length Número de bytes a leer
   * @return true si la lectura fue exitosa
   */
  bool readRegisters(uint8_t reg, uint8_t* buffer, uint8_t length);

  /**
   * @brief Calcula el factor de escala para acelerómetro
   * 
   * @return Factor mg por LSB según rango configurado
   */
  float getAccelScaleFactor() const;

  /**
   * @brief Calcula el factor de escala para giroscopio
   * 
   * @return Factor mdps por LSB según rango configurado
   */
  float getGyroScaleFactor() const;

  // -----------------------------
  // Atributos privados
  // -----------------------------
  uint8_t addr_;               // Dirección I²C (0x68 o 0x69)
  AccelRange accel_range_;     // Rango actual del acelerómetro
  GyroRange gyro_range_;       // Rango actual del giroscopio
  
  // Offsets de calibración (para futuras mejoras)
  int16_t accel_offset_[3];    // Offsets X, Y, Z del acelerómetro
  int16_t gyro_offset_[3];     // Offsets X, Y, Z del giroscopio
  bool calibrated_;            // Flag de calibración realizada
};
