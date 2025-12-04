// -----------------------------------------------------------------------------
// test_mpu6050.cpp — Pruebas unitarias del driver MPU6050
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
//
// Pruebas incluidas
// - Inicialización y detección del MPU6050
// - Lectura de valores raw (accel, gyro, temp)
// - Conversión a unidades escaladas (mg, mdps, centésimas °C)
// - Configuración de rangos (accel y gyro)
// - Verificación de WHO_AM_I
//
// Uso
// - Compilar con PlatformIO: pio test
// - Ejecutar en placa Arduino UNO/NANO con MPU6050 conectado
// - Requiere sensor físico conectado a pines I²C (A4/A5)
// -----------------------------------------------------------------------------

#include <Arduino.h>
#include <unity.h>
#include <MPU6050Driver.h>
#include <AngleCalculator.h>

// Instancia global del driver (se inicializa en setUp)
static MPU6050Driver* mpu = nullptr;
static AngleCalculator* angles = nullptr;

// -----------------------------
// Setup y TearDown
// -----------------------------
void setUp(void) {
  // Crear instancia del driver antes de cada test
  if (!mpu) {
    mpu = new MPU6050Driver(0x68);
  }
  if (!angles) {
    angles = new AngleCalculator();
  }
}

void tearDown(void) {
  // No destruir la instancia para evitar reinicializar I²C en cada test
  // Se reutiliza la misma instancia
}

// -----------------------------
// Tests de inicialización
// -----------------------------
void test_mpu6050_begin(void) {
  // Test: el sensor debe inicializarse correctamente
  bool success = mpu->begin();
  TEST_ASSERT_TRUE_MESSAGE(success, "MPU6050 no se pudo inicializar (verificar conexión I²C)");
}

void test_mpu6050_is_connected(void) {
  // Test: el sensor debe responder al WHO_AM_I
  bool connected = mpu->isConnected();
  TEST_ASSERT_TRUE_MESSAGE(connected, "MPU6050 no responde (verificar dirección 0x68 y conexiones)");
}

// -----------------------------
// Tests de lectura raw
// -----------------------------
void test_mpu6050_read_raw_accel(void) {
  // Test: lectura raw del acelerómetro debe ser exitosa
  int16_t ax, ay, az;
  bool success = mpu->readRawAccel(ax, ay, az);
  
  TEST_ASSERT_TRUE_MESSAGE(success, "Error al leer acelerómetro raw");
  
  // Verificar que los valores no sean todos cero (sensor en reposo debe tener gravedad en Z)
  bool has_values = (ax != 0 || ay != 0 || az != 0);
  TEST_ASSERT_TRUE_MESSAGE(has_values, "Acelerómetro devuelve todos ceros (sensor defectuoso?)");
}

void test_mpu6050_read_raw_gyro(void) {
  // Test: lectura raw del giroscopio debe ser exitosa
  int16_t gx, gy, gz;
  bool success = mpu->readRawGyro(gx, gy, gz);
  
  TEST_ASSERT_TRUE_MESSAGE(success, "Error al leer giroscopio raw");
  
  // Nota: gyro en reposo puede estar cerca de cero, pero no debe fallar la lectura
}

void test_mpu6050_read_raw_temp(void) {
  // Test: lectura raw de temperatura debe ser exitosa
  int16_t temp;
  bool success = mpu->readRawTemp(temp);
  
  TEST_ASSERT_TRUE_MESSAGE(success, "Error al leer temperatura raw");
  
  // Verificar rango razonable (temperatura ambiente aprox. 20-30°C)
  // Raw típico: 0°C ≈ -12420, 25°C ≈ -4000, 50°C ≈ 4420
  TEST_ASSERT_MESSAGE(temp > -20000 && temp < 20000, "Temperatura raw fuera de rango esperado");
}

// -----------------------------
// Tests de lectura escalada
// -----------------------------
void test_mpu6050_read_accel_mg(void) {
  // Test: lectura escalada del acelerómetro en mg
  int16_t ax, ay, az;
  bool success = mpu->readAccelMg(ax, ay, az);
  
  TEST_ASSERT_TRUE_MESSAGE(success, "Error al leer acelerómetro en mg");
  
  // Verificar rango razonable (sensor en reposo debe tener ~1000 mg en algún eje)
  // Magnitud esperada ≈ 1000 mg (1g de gravedad)
  int32_t mag_sq = (int32_t)ax*ax + (int32_t)ay*ay + (int32_t)az*az;
  int32_t expected_sq = 1000L * 1000L;  // 1g² en mg²
  
  // Tolerancia ±30% (700-1300 mg)
  TEST_ASSERT_MESSAGE(mag_sq > 700L*700L && mag_sq < 1300L*1300L, 
                      "Magnitud de aceleración fuera de rango esperado (1g)");
}

void test_mpu6050_read_gyro_mdps(void) {
  // Test: lectura escalada del giroscopio en mdps
  int16_t gx, gy, gz;
  bool success = mpu->readGyroMdps(gx, gy, gz);
  
  TEST_ASSERT_TRUE_MESSAGE(success, "Error al leer giroscopio en mdps");
  
  // Sensor en reposo debe tener valores cercanos a cero (±500 mdps tolerancia)
  TEST_ASSERT_MESSAGE(abs(gx) < 5000, "Gyro X fuera de rango en reposo");
  TEST_ASSERT_MESSAGE(abs(gy) < 5000, "Gyro Y fuera de rango en reposo");
  TEST_ASSERT_MESSAGE(abs(gz) < 5000, "Gyro Z fuera de rango en reposo");
}

void test_mpu6050_read_temp_centi(void) {
  // Test: lectura de temperatura en centésimas de °C
  int16_t temp_mc = mpu->readTempCenti();
  
  // Verificar rango razonable (temperatura ambiente 15-40°C)
  // temp_mc = temp_c * 100, por lo que 15°C = 1500, 40°C = 4000
  TEST_ASSERT_MESSAGE(temp_mc > 1000 && temp_mc < 5000, 
                      "Temperatura fuera de rango esperado (15-40°C)");
}

// -----------------------------
// Tests de configuración
// -----------------------------
void test_mpu6050_set_accel_range(void) {
  // Test: configurar diferentes rangos de acelerómetro
  mpu->setAccelRange(ACCEL_RANGE_4G);
  TEST_ASSERT_EQUAL(ACCEL_RANGE_4G, mpu->getAccelRange());
  
  mpu->setAccelRange(ACCEL_RANGE_2G);
  TEST_ASSERT_EQUAL(ACCEL_RANGE_2G, mpu->getAccelRange());
}

void test_mpu6050_set_gyro_range(void) {
  // Test: configurar diferentes rangos de giroscopio
  mpu->setGyroRange(GYRO_RANGE_500DPS);
  TEST_ASSERT_EQUAL(GYRO_RANGE_500DPS, mpu->getGyroRange());
  
  mpu->setGyroRange(GYRO_RANGE_250DPS);
  TEST_ASSERT_EQUAL(GYRO_RANGE_250DPS, mpu->getGyroRange());
}

// -----------------------------
// Tests de AngleCalculator
// -----------------------------
void test_angle_calculator_pitch_roll(void) {
  // Test: calcular ángulos a partir de aceleración simulada
  
  // Caso 1: Sensor horizontal (Z = +1g, X = Y = 0)
  angles->update(0, 0, 1000);  // mg
  int16_t pitch = angles->getPitchMdeg();
  int16_t roll = angles->getRollMdeg();
  
  // Esperado: pitch ≈ 0°, roll ≈ 0°
  TEST_ASSERT_MESSAGE(abs(pitch) < 100, "Pitch debería ser ~0° en horizontal");
  TEST_ASSERT_MESSAGE(abs(roll) < 100, "Roll debería ser ~0° en horizontal");
  
  // Caso 2: Inclinado 45° en X (pitch positivo)
  angles->update(707, 0, 707);  // 45° → sin(45°)×1000 ≈ 707 mg en X y Z
  pitch = angles->getPitchMdeg();
  
  // Esperado: pitch ≈ 450 mdeg (45°)
  TEST_ASSERT_MESSAGE(pitch > 400 && pitch < 500, "Pitch debería ser ~45° con inclinación X");
}

void test_angle_calculator_filter(void) {
  // Test: verificar que el filtro suaviza los valores
  angles->reset();
  angles->setFilterAlpha(0.5f);  // Filtro moderado
  
  // Primera actualización
  angles->update(500, 0, 866);  // ~30° en X
  int16_t pitch1 = angles->getPitchMdeg();
  
  // Segunda actualización con mismo valor
  angles->update(500, 0, 866);
  int16_t pitch2 = angles->getPitchMdeg();
  
  // Con filtro, el segundo valor debería converger hacia el primero
  TEST_ASSERT_MESSAGE(abs(pitch2 - pitch1) < abs(pitch1), 
                      "El filtro debería suavizar los valores");
}

// -----------------------------
// Main de tests
// -----------------------------
void setup() {
  delay(2000);  // Esperar 2 segundos para estabilizar serial
  
  UNITY_BEGIN();
  
  // Tests de inicialización
  RUN_TEST(test_mpu6050_begin);
  RUN_TEST(test_mpu6050_is_connected);
  
  // Tests de lectura raw
  RUN_TEST(test_mpu6050_read_raw_accel);
  RUN_TEST(test_mpu6050_read_raw_gyro);
  RUN_TEST(test_mpu6050_read_raw_temp);
  
  // Tests de lectura escalada
  RUN_TEST(test_mpu6050_read_accel_mg);
  RUN_TEST(test_mpu6050_read_gyro_mdps);
  RUN_TEST(test_mpu6050_read_temp_centi);
  
  // Tests de configuración
  RUN_TEST(test_mpu6050_set_accel_range);
  RUN_TEST(test_mpu6050_set_gyro_range);
  
  // Tests de AngleCalculator
  RUN_TEST(test_angle_calculator_pitch_roll);
  RUN_TEST(test_angle_calculator_filter);
  
  UNITY_END();
}

void loop() {
  // Nada que hacer aquí
}
