// -----------------------------------------------------------------------------
// test_i2c_scan.cpp - Escaneo I²C para detectar dispositivos
// Utilidad de diagnóstico para verificar direcciones I²C activas
// -----------------------------------------------------------------------------

#include <Arduino.h>
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); }
  
  Serial.println("\n=== I2C Scanner ===");
  Serial.println("Escaneando bus I2C...\n");
  
  Wire.begin();
  Wire.setClock(400000UL);  // 400 kHz
  
  byte count = 0;
  
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte error = Wire.endTransmission();
    
    if (error == 0) {
      Serial.print("✓ Dispositivo encontrado en 0x");
      if (addr < 16) Serial.print("0");
      Serial.print(addr, HEX);
      Serial.print(" (");
      Serial.print(addr, DEC);
      Serial.println(")");
      
      // Identificar dispositivos conocidos
      if (addr == 0x68 || addr == 0x69) {
        Serial.println("  → Probablemente MPU6050/MPU9250");
      }
      
      count++;
      delay(10);
    } else if (error == 4) {
      Serial.print("✗ Error desconocido en 0x");
      if (addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
    }
  }
  
  Serial.println("\n--- Resumen ---");
  if (count == 0) {
    Serial.println("❌ No se encontraron dispositivos I2C");
    Serial.println("\nVerifica:");
    Serial.println("  • Conexiones SDA/SCL correctas");
    Serial.println("  • Alimentación del sensor (VCC/GND)");
    Serial.println("  • Resistencias pull-up en SDA/SCL");
  } else {
    Serial.print("✓ Encontrados ");
    Serial.print(count);
    Serial.println(" dispositivo(s)");
  }
  
  Serial.println("\n--- Configuración esperada para MPU6050 ---");
  Serial.println("  VCC  → 5V (o 3.3V)");
  Serial.println("  GND  → GND");
  Serial.println("  SCL  → A5 (Arduino UNO/Nano)");
  Serial.println("  SDA  → A4 (Arduino UNO/Nano)");
  Serial.println("  AD0  → GND (dirección 0x68)");
  Serial.println("  AD0  → VCC (dirección 0x69)");
  Serial.println("\nEscaneo completado.");
}

void loop() {
  // Nada que hacer aquí
  delay(1000);
}
