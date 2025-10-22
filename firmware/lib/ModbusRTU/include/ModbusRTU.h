// -----------------------------------------------------------------------------
// <Archivo> — Placeholder (sin lógica)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Cumple norma Modbus RTU (CRC16 0xA001; broadcast sin respuesta).
// -----------------------------------------------------------------------------
#pragma once
// API prevista:
// class ModbusRTU { public: ModbusRTU(uint8_t pinDeRe); void process(); void setUnitId(uint8_t); static uint16_t crc16(const uint8_t*, size_t); };
