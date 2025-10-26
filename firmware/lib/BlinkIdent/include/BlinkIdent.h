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
	explicit BlinkIdent(uint8_t pin);                 // pin: GPIO del LED de identificación
	void begin();                                     // Configura el pin y deja el LED en estado inactivo
	void start(uint16_t timeoutSeconds = 15);         // Inicia patrón con timeout (segundos); 0 = indefinido
	void stop();                                      // Detiene el patrón y apaga el LED
	void update();                                    // Avanza el patrón; llamar frecuentemente en loop()
	bool is_active() const { return active_; }        // Indica si el patrón está activo

 private:
	void driveLed(bool on);                           // Escribe el estado del LED respetando la lógica activa

	uint8_t pin_;                                     // Pin del LED
	bool active_ = false;                             // Estado actual del patrón (activo/inactivo)
	uint32_t startMs_ = 0;                            // Marca temporal de inicio (ms)
	uint32_t timeoutMs_ = 0;                          // Duración total del patrón (ms)
};
