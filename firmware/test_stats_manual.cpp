// Test manual de RollingStats5s
#include <Arduino.h>
#include "RollingStats.h"

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000);
  
  Serial.println("=== Test RollingStats5s ===");
  
  RollingStats5s stats(5000); // Ventana de 5s
  
  uint32_t start = millis();
  int16_t sample = 100;
  
  for (int i = 0; i < 60; i++) {  // 60 muestras en ~6 segundos
    delay(100);
    uint32_t now = millis();
    int16_t min, max, avg;
    
    bool rotated = stats.onSample(now, sample, min, max, avg);
    
    sample += random(-10, 10);  // Variar valor
    
    Serial.print(i);
    Serial.print(": t=");
    Serial.print(now - start);
    Serial.print("ms, sample=");
    Serial.print(sample);
    Serial.print(" -> min=");
    Serial.print(stats.getMin());
    Serial.print(" max=");
    Serial.print(stats.getMax());
    Serial.print(" avg=");
    Serial.print(stats.getAvg());
    
    if (rotated) {
      Serial.print(" [ROTATED! snapshot: min=");
      Serial.print(min);
      Serial.print(" max=");
      Serial.print(max);
      Serial.print(" avg=");
      Serial.print(avg);
      Serial.print("]");
    }
    
    Serial.println();
  }
  
  Serial.println("=== Test completado ===");
}

void loop() {}
