// -----------------------------------------------------------------------------
// test_crc16.cpp — Pruebas unitarias para CRC16 Modbus
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// -----------------------------------------------------------------------------

#include <Arduino.h>
#include <unity.h>
#include "crc16_utils.h"

void test_crc16_known_vector() {
	// Ejemplo clásico: 01 03 00 00 00 0A → CRC esperado 0xCDC5 (LSB=C5, MSB=CD)
	const uint8_t req[] = { 0x01, 0x03, 0x00, 0x00, 0x00, 0x0A };
	uint16_t crc = modbus_crc16(req, sizeof(req));
	TEST_ASSERT_EQUAL_HEX16(0xCDC5, crc);
}

void test_crc16_empty() {
	uint16_t crc = modbus_crc16(nullptr, 0);
	// Implementación devuelve 0xFFFF al iterar cero bytes
	TEST_ASSERT_EQUAL_HEX16(0xFFFF, crc);
}

// Las funciones de test se ejecutan desde otro archivo (test_modbus_map.cpp)
