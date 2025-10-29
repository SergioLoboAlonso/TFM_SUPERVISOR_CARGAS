// -----------------------------------------------------------------------------
// firmware_version.h — Versionado del firmware
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// -----------------------------------------------------------------------------

// Se evitan inclusiones repetidas
#pragma once

// Versión semántica
#ifndef FW_VERSION_GLOBAL
  // Se incrementa en cambios incompatibles; puede sobreescribirse con -D en platformio.ini.
  #define FW_VERSION_GLOBAL 1 // Versión mayor (rompe compatibilidad)
#endif
#ifndef FW_VERSION_MINOR
  // Se incrementa cuando se añaden funcionalidades compatibles.
  #define FW_VERSION_MINOR 0 // Versión menor (compatible)
#endif
#ifndef FW_VERSION_PATCH
  // Se ajusta en correcciones puntuales o builds de mantenimiento.
  #define FW_VERSION_PATCH 0 // Parche/mantenimiento
#endif

// Revisión de hardware (si cambia PCB o cableado)
// Mantener compatibilidad con HW_REV existente y, opcionalmente, habilitar semántica mayor.menor.parche
#ifndef HW_REV
  // Se coordina con la etiqueta serigrafiada en la placa para facilitar depuración en campo.
  #define HW_REV 1 // Revisión de hardware (valor mayor por compatibilidad)
#endif

// Versión de hardware (opcional, mayor.menor.parche)
#ifndef HW_VERSION_MAJOR
  #define HW_VERSION_MAJOR (HW_REV) // Por defecto, usar HW_REV como mayor
#endif
#ifndef HW_VERSION_MINOR
  #define HW_VERSION_MINOR 0
#endif
#ifndef HW_VERSION_PATCH
  #define HW_VERSION_PATCH 0
#endif

// (Opcional) fecha de build fija; puede automatizarse con extra_scripts de PlatformIO
#ifndef FW_BUILD_DATE
  // Debe mantenerse sincronizada con el changelog o generarse automáticamente en cada build.
  #define FW_BUILD_DATE "2025-10-24" // Fecha de compilación
#endif

// Identidad por defecto (puede sobreescribirse con -D VENDOR_NAME=... y -D MODEL_NAME=...)
#ifndef VENDOR_NAME
  #define VENDOR_NAME "LOBO-IoT" // Fabricante
#endif
#ifndef MODEL_NAME
  #define MODEL_NAME  "Inclino_TX" // Modelo
#endif

// Cadena formateada para impresión, p. ej.: "v1.0.0 (HW1.0.0) 2025-10-24"
#define FW_VERSION_STR  "v" STR(FW_VERSION_GLOBAL) "." STR(FW_VERSION_MINOR) "." STR(FW_VERSION_PATCH) " (HW" STR(HW_VERSION_MAJOR) "." STR(HW_VERSION_MINOR) "." STR(HW_VERSION_PATCH) ") " FW_BUILD_DATE // Cadena de versión formateada

// Macros de ayuda para conversión a texto (stringify)
#define STR_HELPER(x) #x // Macro auxiliar para convertir a cadena
#define STR(x) STR_HELPER(x) // Convierte macro numérica a texto

// Versión semántica empaquetada como entero 0xMMmmpp (8b/8b/8b)
#define FW_SEMVER_U32  ((uint32_t)((FW_VERSION_GLOBAL & 0xFF) << 16) | ((FW_VERSION_MINOR & 0xFF) << 8) | (FW_VERSION_PATCH & 0xFF)) // SemVer empaquetado MM.mm.pp

// Longitudes para identidad ASCII en registros Modbus (ver registers.h)
#define ID_STR_FIXED_BYTES   16  // VENDOR y MODEL ocupan 16B (8 registros)
#define ALIAS_MAX_BYTES      64  // Alias máximo permitido (32 registros)

// -----------------------------------------------------------------------------
// Helpers de identidad — construcción de cadena ASCII compacta para Identify
// Formato: "VENDOR=<VENDOR_NAME>;MODEL=<MODEL_NAME>;FW=<FW_VERSION_STR>"
// Devuelve la longitud escrita (sin incluir terminador NUL). Siempre termina en NUL.
// Nota: pensado para AVR; evita snprintf para reducir huella.
// -----------------------------------------------------------------------------
static inline uint8_t fv__append(char* out, uint8_t pos, uint8_t cap, const char* s){
  if(cap == 0) return pos;
  while(*s && pos < (uint8_t)(cap - 1)) { out[pos++] = *s++; }
  out[pos] = '\0';
  return pos;
}

static inline uint8_t fv_build_identity_ascii(char* out, uint8_t cap){
  uint8_t pos = 0;
  pos = fv__append(out, pos, cap, "VENDOR=");
  pos = fv__append(out, pos, cap, VENDOR_NAME);
  pos = fv__append(out, pos, cap, ";MODEL=");
  pos = fv__append(out, pos, cap, MODEL_NAME);
  pos = fv__append(out, pos, cap, ";FW=");
  pos = fv__append(out, pos, cap, FW_VERSION_STR);
  return pos;
}
