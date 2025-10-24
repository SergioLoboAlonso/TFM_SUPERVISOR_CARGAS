// -----------------------------------------------------------------------------
// crc16_utils.h — Utilidades CRC16 para Modbus RTU
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Implementa el CRC16 estándar de Modbus (polinomio 0xA001, init 0xFFFF).
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>

// Calcula el CRC16 (Modbus RTU) sobre el buffer [data,len].
// - Polinomio: 0xA001
// - Valor inicial: 0xFFFF
// Retorna el CRC en formato little-endian (LSB en el primer byte transmitido).
uint16_t modbus_crc16(const uint8_t* data, size_t len);

