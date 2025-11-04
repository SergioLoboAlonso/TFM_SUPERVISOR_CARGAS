// -----------------------------------------------------------------------------
// EepromUtils.cpp — Acceso simple a EEPROM (UnitID, Serial, Alias)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Layout mínimo, con encabezado de magic/version para validar contenido.
// -----------------------------------------------------------------------------

#include "EepromUtils.h"
#include <avr/eeprom.h>

namespace {
	// Layout simple en EEPROM (bytes):
	// 0x00..0x01: MAGIC 0xB5, 0x7A ("µz"), marca de inicialización
	// 0x02:      VERSION = 0x01
	// 0x03:      reservado
	// 0x04..0x05: UnitID (uint16_t)
	// 0x06..0x09: Serial (uint32_t)
	// 0x0A..0x0B: Alias length (uint16_t)
	// 0x0C..0x4B: Alias bytes (máx 64)
	const uint8_t  MAGIC0 = 0xB5;  // Marca de inicialización (byte 0)
	const uint8_t  MAGIC1 = 0x7A;  // Marca de inicialización (byte 1)
	const uint8_t  VERSION = 0x01; // Versión de layout de EEPROM

	const int OFF_MAGIC0   = 0x00; // Offset MAGIC0
	const int OFF_MAGIC1   = 0x01; // Offset MAGIC1
	const int OFF_VERSION  = 0x02; // Offset VERSION
	const int OFF_UNITID   = 0x04; // Offset UnitID (uint16)
	const int OFF_SERIAL   = 0x06; // Offset Serial (uint32)
	const int OFF_ALIASLEN = 0x0A; // Offset longitud alias (uint16)
	const int OFF_ALIAS    = 0x0C; // Offset base alias (hasta 64B)

	bool headerValid() {
		return (eeprom_read_byte((uint8_t*)OFF_MAGIC0) == MAGIC0) && (eeprom_read_byte((uint8_t*)OFF_MAGIC1) == MAGIC1) && (eeprom_read_byte((uint8_t*)OFF_VERSION) == VERSION);
	}

	void ensureHeader() {
		if (!headerValid()) {
			eeprom_update_byte((uint8_t*)OFF_MAGIC0, MAGIC0);
			eeprom_update_byte((uint8_t*)OFF_MAGIC1, MAGIC1);
			eeprom_update_byte((uint8_t*)OFF_VERSION, VERSION);
			// Default values
			eeprom_update_word((uint16_t*)OFF_UNITID, (uint16_t)0);
			eeprom_update_dword((uint32_t*)OFF_SERIAL, (uint32_t)0);
			eeprom_update_word((uint16_t*)OFF_ALIASLEN, (uint16_t)0);
			for (int i = 0; i < 64; ++i) eeprom_update_byte((uint8_t*)(OFF_ALIAS + i), 0); // Limpia zona de alias
		}
	}
}

namespace EepromUtils {

void begin() {
	ensureHeader();
}

uint16_t readUnitId() {
	if (!headerValid()) return 0;
		uint16_t v = eeprom_read_word((uint16_t*)OFF_UNITID);
	return v;
}

void writeUnitId(uint16_t uid) {
	ensureHeader();
	eeprom_update_word((uint16_t*)OFF_UNITID, uid);
}

uint32_t readSerial() {
	if (!headerValid()) return 0;
		uint32_t s = eeprom_read_dword((uint32_t*)OFF_SERIAL);
	return s;
}

void writeSerial(uint32_t serial) {
	ensureHeader();
	eeprom_update_dword((uint32_t*)OFF_SERIAL, serial);
}

void readAlias(char* out, uint16_t& len) {
	if (!out) return;
	if (!headerValid()) {
		// Si no hay cabecera válida aún, expone alias por defecto en memoria
		const char* def = "default";
		uint16_t i = 0;
		while (def[i] && i < 64) { out[i] = def[i]; i++; }
		out[i] = '\0';
		len = i;
		return;
	}
	// Longitud leída de alias (acotada a 64)
	uint16_t l = eeprom_read_word((uint16_t*)OFF_ALIASLEN);
	if (l > 64) l = 64;
	if (l == 0) {
		// Si no está provisionado, devuelve alias por defecto sin escribir en EEPROM
		const char* def = "default";
		uint16_t i = 0;
		while (def[i] && i < 64) { out[i] = def[i]; i++; }
		out[i] = '\0';
		len = i;
		return;
	}
	for (uint16_t i = 0; i < l; ++i) {
		out[i] = static_cast<char>(eeprom_read_byte((uint8_t*)(OFF_ALIAS + i)));
	}
	out[l] = '\0';
	len = l;
}

void writeAlias(const char* in, uint16_t len) {
	ensureHeader();
	if (!in) { eeprom_update_word((uint16_t*)OFF_ALIASLEN, (uint16_t)0); return; }
	uint16_t l = len > 64 ? 64 : len;
	eeprom_update_word((uint16_t*)OFF_ALIASLEN, l);
	for (uint16_t i = 0; i < l; ++i) {
		eeprom_update_byte((uint8_t*)(OFF_ALIAS + i), (uint8_t)in[i]);
	}
	for (uint16_t i = l; i < 64; ++i) {
		eeprom_update_byte((uint8_t*)(OFF_ALIAS + i), 0);
	}
}

} // namespace EepromUtils

