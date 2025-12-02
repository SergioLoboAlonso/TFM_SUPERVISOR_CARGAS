"""
============================================================================
DATA NORMALIZER - Conversión de Datos Modbus a Unidades Físicas
============================================================================

Responsabilidades:
    1. Conversión de registros Modbus (int16/uint16) a valores físicos
    2. Decodificación de strings ASCII (alias, vendor, product)
    3. Codificación de strings para escritura Modbus
    4. Interpretación de bitmasks (capacidades, estado, errores)

Tabla de Conversiones (según especificación firmware):
    +------------------+-------------+------------+------------------+
    | Magnitud         | Unidad Modbus| Escala    | Unidad Física   |
    +------------------+-------------+------------+------------------+
    | Ángulo X/Y       | mdeg        | ×100       | grados (°)      |
    | Temperatura      | mc          | ×100       | °Celsius        |
    | Aceleración      | mg          | ×1000      | g (gravedad)    |
    | Giroscopio       | mdps        | ×1000      | °/s             |
    | Viento           | cm/s ×100   | ×100       | m/s (y km/h)    |
    | Muestras         | 2x uint16   | LSW+MSW    | uint32          |
    +------------------+-------------+------------+------------------+

Formato ASCII (alias, vendor, product):
    - Empaquetado: 2 bytes por registro (big-endian)
    - MSB primero: registro = (char1 << 8) | char2
    - Ejemplo: 'AB' → 0x4142

============================================================================
"""
from typing import Dict, Any


class DataNormalizer:
    """Normaliza datos de registros Modbus a unidades físicas"""
    
    @staticmethod
    def normalize_telemetry(raw_regs: list, capabilities: list = None) -> Dict[str, Any]:
        """
        Normaliza telemetría desde Input Registers (IR).
        
        Args:
            raw_regs: Lista de 13 registros leídos desde IR addr=0x0000
                [0] IR_MED_ANGULO_X_CDEG (int16, ×100 → °)
                [1] IR_MED_ANGULO_Y_CDEG (int16, ×100 → °)
                [2] IR_MED_TEMPERATURA_CENTI (int16, ×100 → °C)
                [3] IR_MED_ACEL_X_mG (int16, mg → g)
                [4] IR_MED_ACEL_Y_mG (int16, mg → g)
                [5] IR_MED_ACEL_Z_mG (int16, mg → g)
                [6] IR_MED_GIRO_X_mdps (int16, mdps → °/s)
                [7] IR_MED_GIRO_Y_mdps (int16, mdps → °/s)
                [8] IR_MED_GIRO_Z_mdps (int16, mdps → °/s)
                [9] IR_MED_MUESTRAS_LO (uint16, LSW)
                [10] IR_MED_MUESTRAS_HI (uint16, MSW)
                [11] IR_MED_FLAGS_CALIDAD (uint16, bitmask)
                [12] IR_MED_PESO_KG (int16, kg sin decimales)
            capabilities: Lista de capabilities del dispositivo (ej: ['RS485', 'MPU6050', 'Load'])
        
        Returns:
            Dict con telemetría normalizada (solo campos de sensores habilitados)
        """
        if len(raw_regs) < 13:
            raise ValueError(f"Se esperan >=13 registros base, recibidos {len(raw_regs)}")
        
        # Conversión de uint16 a int16 (complemento a 2)
        def to_int16(val: int) -> int:
            return val if val < 32768 else val - 65536
        
        # Conversión de 2× uint16 a uint32
        def to_uint32(lo: int, hi: int) -> int:
            return (hi << 16) | lo
        
        # Normalizar capabilities para comparación case-insensitive
        caps = [c.lower() for c in (capabilities or [])]
        has_mpu = 'mpu6050' in caps
        has_load = 'load' in caps
        has_wind = 'wind' in caps
        
        telemetry = {
            'sample_count': to_uint32(raw_regs[9], raw_regs[10]),
            'quality_flags': raw_regs[11]
        }
        
        # Solo incluir datos de MPU6050 si tiene la capability
        if has_mpu:
            telemetry['angle_x_deg'] = to_int16(raw_regs[0]) / 100.0
            telemetry['angle_y_deg'] = to_int16(raw_regs[1]) / 100.0
            telemetry['temperature_c'] = to_int16(raw_regs[2]) / 100.0
            telemetry['acceleration'] = {
                'x_g': to_int16(raw_regs[3]) / 1000.0,
                'y_g': to_int16(raw_regs[4]) / 1000.0,
                'z_g': to_int16(raw_regs[5]) / 1000.0
            }
            telemetry['gyroscope'] = {
                'x_dps': to_int16(raw_regs[6]) / 1000.0,
                'y_dps': to_int16(raw_regs[7]) / 1000.0,
                'z_dps': to_int16(raw_regs[8]) / 1000.0
            }
        
        # Solo incluir datos de Load si tiene la capability
        if has_load:
            # Firmware almacena centi-kg (1 ckg = 10g): load_g / 10 → ckg
            # Para mostrar en gramos: ckg * 10 → g
            # Para mostrar en kg: ckg / 100 → kg
            telemetry['load_g'] = to_int16(raw_regs[12]) * 10.0  # ckg → gramos
            telemetry['load_kg'] = to_int16(raw_regs[12]) / 100.0  # ckg → kg

        # Ampliaciones opcionales (viento + estadísticas + carga) si el bloque incluye más registros.
        # Layout extendido (cuando se leen 28 registros):
        # [13] wind_speed_cmps (int16, ×100 → cm/s)
        # [14] wind_direction_deg (uint16)
        # [15] wind_min_cmps
        # [16] wind_max_cmps
        # [17] wind_avg_cmps
        # [18..26] accel stats (x_min, x_max, x_avg, y_min, y_max, y_avg, z_min, z_max, z_avg) en mG
        # [27] load_max_100_kg (int16, kg×100) - máximo de las últimas 100 muestras
        
        # Viento: solo si tiene la capability Wind
        if has_wind and len(raw_regs) >= 15:  # viento actual presente (indices 13,14)
            wind_speed_mps = raw_regs[13] / 100.0  # firmware expone cm/s *? (definido como cm/s ×100 ⇒ m/s = cm/s/100)
            # Clarificar conversión: registro almacena cm/s *1 → se decidió escalar ×100 para resolución centi-cm/s.
            # km/h = m/s * 3.6
            wind_speed_kmh = wind_speed_mps * 3.6
            telemetry['wind_speed_mps'] = wind_speed_mps
            telemetry['wind_speed_kmh'] = wind_speed_kmh
            telemetry['wind_direction_deg'] = raw_regs[14]
        
        if has_wind and len(raw_regs) >= 18:  # estadísticas de viento (min/max/avg)
            wind_min_mps = raw_regs[15] / 100.0
            wind_max_mps = raw_regs[16] / 100.0
            wind_avg_mps = raw_regs[17] / 100.0
            telemetry['wind_stats'] = {
                'min_mps': wind_min_mps,
                'max_mps': wind_max_mps,
                'avg_mps': wind_avg_mps,
                'min_kmh': wind_min_mps * 3.6,
                'max_kmh': wind_max_mps * 3.6,
                'avg_kmh': wind_avg_mps * 3.6
            }
        
        # Estadísticas de acelerómetro: solo si tiene MPU6050
        if has_mpu and len(raw_regs) >= 27:  # estadísticas acelerómetro completas
            def mg_to_g(val: int) -> float:
                return (val if val < 32768 else val - 65536) / 1000.0
            accel_stats_regs = raw_regs[18:27]
            
            if len(accel_stats_regs) == 9:
                x_min, x_max, x_avg, y_min, y_max, y_avg, z_min, z_max, z_avg = accel_stats_regs
                telemetry['acceleration_stats'] = {
                    'x_g': {
                        'min': mg_to_g(x_min),
                        'max': mg_to_g(x_max),
                        'avg': mg_to_g(x_avg)
                    },
                    'y_g': {
                        'min': mg_to_g(y_min),
                        'max': mg_to_g(y_max),
                        'avg': mg_to_g(y_avg)
                    },
                    'z_g': {
                        'min': mg_to_g(z_min),
                        'max': mg_to_g(z_max),
                        'avg': mg_to_g(z_avg)
                    }
                }
        
        # Máximo de 100 muestras de carga (índice 27): solo si tiene capability Load
        if has_load and len(raw_regs) >= 28:
            load_max_100_raw = raw_regs[27]
            telemetry['load_max_100_kg'] = to_int16(load_max_100_raw) / 100.0
        
        return telemetry
    
    @staticmethod
    def decode_alias(alias_len: int, alias_regs: list) -> str:
        """
        Decodifica alias desde registros ASCII (big-endian, 2B/reg).
        
        Args:
            alias_len: Longitud del alias en bytes (0..64)
            alias_regs: Lista de hasta 32 registros con alias empaquetado
        
        Returns:
            String alias decodificado
        """
        if alias_len == 0:
            return ""
        
        if alias_len > 64:
            alias_len = 64  # Límite de seguridad
        
        # Desempaquetar registros (MSB→LSB por registro)
        bytes_data = []
        for reg in alias_regs:
            bytes_data.append((reg >> 8) & 0xFF)  # MSB
            bytes_data.append(reg & 0xFF)          # LSB
        
        # Tomar solo los bytes necesarios según alias_len
        alias_bytes = bytes_data[:alias_len]
        
        # Decodificar ASCII (ignorar caracteres no imprimibles)
        try:
            alias_str = bytes(alias_bytes).decode('ascii', errors='ignore')
            return alias_str.strip('\x00')  # Remover null terminators
        except Exception:
            return ""
    
    @staticmethod
    def encode_alias(alias_str: str) -> tuple[int, list]:
        """
        Codifica alias a formato Modbus (big-endian, 2B/reg).
        
        Args:
            alias_str: String alias (máx 64 caracteres ASCII)
        
        Returns:
            Tupla (longitud_bytes, lista_registros)
        """
        # Validar y truncar si excede límite
        alias_bytes = alias_str.encode('ascii', errors='ignore')[:64]
        alias_len = len(alias_bytes)
        
        # Pad con 0x00 si longitud impar
        if alias_len % 2 != 0:
            alias_bytes += b'\x00'
        
        # Empaquetar en registros (MSB→LSB)
        registers = []
        for i in range(0, len(alias_bytes), 2):
            msb = alias_bytes[i]
            lsb = alias_bytes[i+1] if i+1 < len(alias_bytes) else 0x00
            registers.append((msb << 8) | lsb)
        
        return alias_len, registers
    
    @staticmethod
    def decode_vendor_product(vendor_id: int, product_id: int) -> tuple[str, str]:
        """
        Decodifica vendor_id y product_id a strings.
        
        Args:
            vendor_id: 0x4C6F = 'Lo'
            product_id: 0x426F = 'Bo'
        
        Returns:
            Tupla (vendor_str, product_str)
        """
        vendor_str = chr((vendor_id >> 8) & 0xFF) + chr(vendor_id & 0xFF)
        product_str = chr((product_id >> 8) & 0xFF) + chr(product_id & 0xFF)
        return vendor_str, product_str
    
    @staticmethod
    def decode_version(version_reg: int) -> str:
        """
        Decodifica versión (major<<8 | minor).
        
        Args:
            version_reg: Registro con versión empaquetada
        
        Returns:
            String "major.minor" (ej. "0.3")
        """
        major = (version_reg >> 8) & 0xFF
        minor = version_reg & 0xFF
        return f"{major}.{minor}"
    
    @staticmethod
    def decode_capabilities(cap_reg: int) -> list[str]:
        """
        Decodifica bitmask de capacidades.
        
        Args:
            cap_reg: HR_INFO_CAPACIDADES (0x0005)
                Bit 0: RS485
                Bit 1: MPU6050
                Bit 2: Identify
                Bit 3: Wind (anemómetro analógico)
                Bit 4: Load (sensor de carga HX711)
        
        Returns:
            Lista de strings con capacidades activas
        """
        capabilities = []
        if cap_reg & (1 << 0):
            capabilities.append("RS485")
        if cap_reg & (1 << 1):
            capabilities.append("MPU6050")
        if cap_reg & (1 << 2):
            capabilities.append("Identify")
        if cap_reg & (1 << 3):
            capabilities.append("Wind")
        if cap_reg & (1 << 4):
            capabilities.append("Load")
        return capabilities
    
    @staticmethod
    def decode_status_flags(status_reg: int) -> list[str]:
        """
        Decodifica bitmask de estado (HR_INFO_ESTADO).
        
        Args:
            status_reg: Registro de estado (0x0008)
                Bit 0: OK
                Bit 1: MPU_READY
                Bit 2: CFG_DIRTY
        
        Returns:
            Lista de flags activos
        """
        flags = []
        if status_reg & (1 << 0):
            flags.append("OK")
        if status_reg & (1 << 1):
            flags.append("MPU_READY")
        if status_reg & (1 << 2):
            flags.append("CFG_DIRTY")
        return flags
    
    @staticmethod
    def decode_error_flags(error_reg: int) -> list[str]:
        """
        Decodifica bitmask de errores (HR_INFO_ERRORES).
        
        Args:
            error_reg: Registro de errores (0x0009)
                Bit 0: MPU_COMM_ERROR
                Bit 1: EEPROM_ERROR
                Bit 2: RANGE_ERROR
        
        Returns:
            Lista de flags de error activos
        """
        flags = []
        if error_reg & (1 << 0):
            flags.append("MPU_COMM_ERROR")
        if error_reg & (1 << 1):
            flags.append("EEPROM_ERROR")
        if error_reg & (1 << 2):
            flags.append("RANGE_ERROR")
        return flags
