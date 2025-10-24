// -----------------------------------------------------------------------------
// EepromUtils.cpp — Acceso simple a EEPROM (UnitID, Serial, Alias)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Layout mínimo, con encabezado de magic/version para validar contenido.
// -----------------------------------------------------------------------------

#include "EepromUtils.h"
#include <EEPROM.h>

namespace {
	// Layout simple en EEPROM (bytes):
	// 0x00..0x01: MAGIC 0xB5, 0x7A ("µz"), marca de inicialización
	// 0x02:      VERSION = 0x01
	// 0x03:      reservado
	// 0x04..0x05: UnitID (uint16_t)
	// 0x06..0x09: Serial (uint32_t)
	// 0x0A..0x0B: Alias length (uint16_t)
	// 0x0C..0x4B: Alias bytes (máx 64)
	const uint8_t  MAGIC0 = 0xB5;
	const uint8_t  MAGIC1 = 0x7A;
	const uint8_t  VERSION = 0x01;

	const int OFF_MAGIC0   = 0x00;
	const int OFF_MAGIC1   = 0x01;
	const int OFF_VERSION  = 0x02;
	const int OFF_UNITID   = 0x04;
	const int OFF_SERIAL   = 0x06;
	const int OFF_ALIASLEN = 0x0A;
	const int OFF_ALIAS    = 0x0C;

	bool headerValid() {
		return (EEPROM.read(OFF_MAGIC0) == MAGIC0) && (EEPROM.read(OFF_MAGIC1) == MAGIC1) && (EEPROM.read(OFF_VERSION) == VERSION);
	}

	void ensureHeader() {
		if (!headerValid()) {
			EEPROM.update(OFF_MAGIC0, MAGIC0);
			EEPROM.update(OFF_MAGIC1, MAGIC1);
			EEPROM.update(OFF_VERSION, VERSION);
			// Default values
			EEPROM.put(OFF_UNITID, static_cast<uint16_t>(0));
			EEPROM.put(OFF_SERIAL, static_cast<uint32_t>(0));
			EEPROM.put(OFF_ALIASLEN, static_cast<uint16_t>(0));
			for (int i = 0; i < 64; ++i) EEPROM.update(OFF_ALIAS + i, 0);
		}
	}
}

namespace EepromUtils {

void begin() {
	// En AVR no es necesario inicializar EEPROM.
	ensureHeader();
}

uint16_t readUnitId() {
	if (!headerValid()) return 0;
	uint16_t v = 0;
	EEPROM.get(OFF_UNITID, v);
	return v;
}

void writeUnitId(uint16_t uid) {
	ensureHeader();
	EEPROM.put(OFF_UNITID, uid);
}

uint32_t readSerial() {
	if (!headerValid()) return 0;
	uint32_t s = 0;
	EEPROM.get(OFF_SERIAL, s);
	return s;
}

void writeSerial(uint32_t serial) {
	ensureHeader();
	EEPROM.put(OFF_SERIAL, serial);
}

void readAlias(char* out, uint16_t& len) {
	if (!out) return;
	if (!headerValid()) { len = 0; out[0] = '\0'; return; }
	uint16_t l = 0;
	EEPROM.get(OFF_ALIASLEN, l);
	if (l > 64) l = 64;
	for (uint16_t i = 0; i < l; ++i) {
		out[i] = static_cast<char>(EEPROM.read(OFF_ALIAS + i));
	}
	out[l] = '\0';
	len = l;
}

void writeAlias(const char* in, uint16_t len) {
	ensureHeader();
	if (!in) { EEPROM.put(OFF_ALIASLEN, static_cast<uint16_t>(0)); return; }
	uint16_t l = len > 64 ? 64 : len;
	EEPROM.put(OFF_ALIASLEN, l);
	for (uint16_t i = 0; i < l; ++i) {
		EEPROM.update(OFF_ALIAS + i, static_cast<uint8_t>(in[i]));
	}
	for (uint16_t i = l; i < 64; ++i) {
		EEPROM.update(OFF_ALIAS + i, 0);
	}
}

} // namespace EepromUtils

