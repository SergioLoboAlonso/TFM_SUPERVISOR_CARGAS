// -----------------------------------------------------------------------------
// BlinkIdent — Control del parpadeo de identificación visual
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>

// Clase sencilla para gestionar un patrón de identificación visual en un LED.
// Uso típico:
//   BlinkIdent ident(IDENT_LED_PIN);
//   ident.begin();
//   ident.start(15); // 15 segundos de patrón de doble parpadeo
//   en loop(): ident.update();
// Patrón: doble parpadeo rápido dentro de una ventana de 1 segundo (150ms ON,
//         150ms OFF, 150ms ON, resto en OFF), repetido hasta timeout.
class BlinkIdent {
 public:
	explicit BlinkIdent(uint8_t pin);
	void begin();
	void start(uint16_t timeoutSeconds = 15);
	void stop();
	void update();
	bool active() const { return active_; }

 private:
	void driveLed(bool on);

	uint8_t pin_;
	bool active_ = false;
	uint32_t startMs_ = 0;
	uint32_t timeoutMs_ = 0;
};
