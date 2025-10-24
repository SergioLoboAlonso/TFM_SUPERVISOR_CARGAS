// -----------------------------------------------------------------------------
// EepromUtils.h — Acceso simple a EEPROM (UnitID, Serial, Alias)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Diseño mínimo y portátil para AVR. En AVR, EEPROM no requiere begin().
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>

namespace EepromUtils {

// Inicialización del backend EEPROM. En AVR no es necesaria, pero se expone
// para mantener portabilidad futura (ESP requiere EEPROM.begin(N)).
void begin();

// Lectura/escritura de UnitID (1..247). Si no se ha provisionado, retorna 0.
uint16_t readUnitId();
void     writeUnitId(uint16_t uid);

// Serial de fábrica (32-bit en MVP). Si no hay valor, retorna 0.
uint32_t readSerial();
void     writeSerial(uint32_t serial);

// Alias ASCII (0..64B). 'out' debe admitir 65B para incluir terminador NUL.
void readAlias(char* out, uint16_t& len);
void writeAlias(const char* in, uint16_t len);

} // namespace EepromUtils

