// -----------------------------------------------------------------------------
// SensorConfig.h — Configuración de sensores por compilación
// Define qué tipos de sensores están habilitados e instancias por nodo.
// Estas macros pueden sobreescribirse desde platformio.ini (build_flags).
// -----------------------------------------------------------------------------
#pragma once

// Habilitación por tipo (0/1)
#ifndef SENSORS_MPU_ENABLED
#define SENSORS_MPU_ENABLED 1
#endif

#ifndef SENSORS_TEMP_ENABLED
#define SENSORS_TEMP_ENABLED 0
#endif

#ifndef SENSORS_ACCEL_ENABLED
#define SENSORS_ACCEL_ENABLED 0
#endif

#ifndef SENSORS_LOAD_ENABLED
#define SENSORS_LOAD_ENABLED 0
#endif

// Número de instancias por tipo (por defecto 1 si habilitado, 0 si no)
#ifndef SENSORS_MPU_COUNT
#define SENSORS_MPU_COUNT (SENSORS_MPU_ENABLED ? 1 : 0)
#endif

#ifndef SENSORS_TEMP_COUNT
#define SENSORS_TEMP_COUNT (SENSORS_TEMP_ENABLED ? 1 : 0)
#endif

#ifndef SENSORS_ACCEL_COUNT
#define SENSORS_ACCEL_COUNT (SENSORS_ACCEL_ENABLED ? 1 : 0)
#endif

#ifndef SENSORS_LOAD_COUNT
#define SENSORS_LOAD_COUNT (SENSORS_LOAD_ENABLED ? 1 : 0)
#endif

// Modo MOCK (0/1): genera datos sintéticos para desarrollo sin hardware
#ifndef SENSORS_USE_MOCK
#define SENSORS_USE_MOCK 0
#endif
