// -----------------------------------------------------------------------------
// crc16_utils.h — Utilidades CRC16 para Modbus RTU
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Implementa el CRC16 estándar de Modbus (polinomio 0xA001, init 0xFFFF).
// -----------------------------------------------------------------------------
#pragma once  // Evita inclusión múltiple del archivo de cabecera

#include <Arduino.h>  // Tipos base y utilidades de Arduino (uint8_t, size_t, etc.)

// Calcula el CRC16 (Modbus RTU) sobre el buffer [data,len].
// - Polinomio: 0xA001 (reflejado)
// - Valor inicial: 0xFFFF
// Retorna el CRC en formato little-endian (LSB en el primer byte transmitido).
uint16_t modbus_crc16(const uint8_t* data, size_t len);  // Calcula y devuelve el CRC16 Modbus

