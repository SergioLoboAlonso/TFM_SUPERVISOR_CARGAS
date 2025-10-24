// -----------------------------------------------------------------------------
// firmware_version.h — Versionado del firmware
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// -----------------------------------------------------------------------------
#pragma once

// Versión semántica
#ifndef FW_VERSION_MAJOR
  // Incrementa en cambios incompatibles; sobreescribe con -D en platformio.ini si hace falta.
  #define FW_VERSION_MAJOR 1
#endif
#ifndef FW_VERSION_MINOR
  // Incrementa cuando añadas funcionalidades compatibles.
  #define FW_VERSION_MINOR 0
#endif
#ifndef FW_VERSION_PATCH
  // Ajusta en correcciones puntuales o builds de mantenimiento.
  #define FW_VERSION_PATCH 0
#endif

// Revisión de hardware (si cambias PCB o cableado)
#ifndef HW_REV
  // Coordínalo con la etiqueta serigrafiada en la placa para depuraciones en campo.
  #define HW_REV 1
#endif

// (Opcional) fecha de build fija; si quieres automatizarla se puede hacer con extra_scripts de PlatformIO
#ifndef FW_BUILD_DATE
  // Mantén este valor sincronizado con el changelog o genera uno automático en cada build.
  #define FW_BUILD_DATE "2025-10-24"
#endif

// Macro útil para imprimir "1.0.0 (HW1) 2025-10-24"
#define FW_VERSION_STR  "v" STR(FW_VERSION_MAJOR) "." STR(FW_VERSION_MINOR) "." STR(FW_VERSION_PATCH) " (HW" STR(HW_REV) ") " FW_BUILD_DATE

// Helpers para stringify
#define STR_HELPER(x) #x
#define STR(x) STR_HELPER(x)
