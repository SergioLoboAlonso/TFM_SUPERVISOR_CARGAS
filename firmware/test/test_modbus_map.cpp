// -----------------------------------------------------------------------------
// test_modbus_map.cpp — Pruebas del mapa de registros Modbus (rangos y semántica básica)
// -----------------------------------------------------------------------------
#include <Arduino.h>
#include <unity.h>

#include <registersModbus.h>

static uint16_t tmp[4];

// Declaraciones de tests adicionales definidos en otros archivos
extern void test_crc16_known_vector();
extern void test_crc16_empty();

void setUp() {
  // Se llama antes de cada test
}

void tearDown() {
  // Se llama después de cada test
}

void test_input_read_min_max() {
  regs_init();
  // Lecturas válidas en bordes
  TEST_ASSERT_TRUE(regs_read_input(IR_MIN_ADDR, 1, tmp));
  TEST_ASSERT_TRUE(regs_read_input(IR_MAX_ADDR, 1, tmp));
  // Ventana que se sale por 1 palabra debe fallar
  TEST_ASSERT_FALSE(regs_read_input(IR_MAX_ADDR, 2, tmp));
}

void test_holding_read_min_max() {
  regs_init();
  TEST_ASSERT_TRUE(regs_read_holding(HR_MIN_ADDR, 1, tmp));
  TEST_ASSERT_TRUE(regs_read_holding(HR_MAX_ADDR, 1, tmp));
  TEST_ASSERT_FALSE(regs_read_holding(HR_MAX_ADDR, 2, tmp));
}

void test_holding_write_valid_command() {
  regs_init();
  // Escribir comando Identify debe ser válido
  TEST_ASSERT_TRUE(regs_write_holding(HR_CMD_IDENT_SEGUNDOS, 5));
  // Debe hacerse eco al leer
  uint16_t val = 0;
  TEST_ASSERT_TRUE(regs_read_holding(HR_CMD_IDENT_SEGUNDOS, 1, &val));
  TEST_ASSERT_EQUAL_HEX16(5, val);
}

void test_holding_write_illegal_address() {
  regs_init();
  // No se permite escribir sobre info de sólo lectura
  TEST_ASSERT_FALSE(regs_write_holding(HR_INFO_VENDOR_ID, 0x1234));
}

void test_diag_increment() {
  regs_init();
  uint16_t before = 0, after = 0;
  // Lee valor actual
  TEST_ASSERT_TRUE(regs_read_holding(HR_DIAG_TRAMAS_RX_OK, 1, &before));
  // Incrementa
  regs_diag_inc(HR_DIAG_TRAMAS_RX_OK);
  // Lee de nuevo
  TEST_ASSERT_TRUE(regs_read_holding(HR_DIAG_TRAMAS_RX_OK, 1, &after));
  TEST_ASSERT_EQUAL_UINT16(before + 1, after);
}

void setup() {
  UNITY_BEGIN();
  // CRC16
  RUN_TEST(test_crc16_known_vector);
  RUN_TEST(test_crc16_empty);
  // Mapa de registros
  RUN_TEST(test_input_read_min_max);
  RUN_TEST(test_holding_read_min_max);
  RUN_TEST(test_holding_write_valid_command);
  RUN_TEST(test_holding_write_illegal_address);
  RUN_TEST(test_diag_increment);
  UNITY_END();
}

void loop() {}
