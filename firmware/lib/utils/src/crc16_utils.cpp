// -----------------------------------------------------------------------------
// crc16_utils.cpp — Utilidades CRC16 para Modbus RTU
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Implementa el algoritmo clásico de CRC16 Modbus (poly 0xA001).
// -----------------------------------------------------------------------------

#include "crc16_utils.h"

uint16_t modbus_crc16(const uint8_t* data, size_t len) {
	uint16_t crc = 0xFFFF;
	for (size_t i = 0; i < len; ++i) {
		crc ^= static_cast<uint16_t>(data[i]);
		for (uint8_t b = 0; b < 8; ++b) {
			if (crc & 0x0001) {
				crc = (crc >> 1) ^ 0xA001;
			} else {
				crc >>= 1;
			}
		}
	}
	return crc;
}

