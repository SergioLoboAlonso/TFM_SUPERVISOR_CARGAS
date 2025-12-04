#!/usr/bin/env python3
"""
============================================================================
EDGE CLI - Interfaz de Línea de Comandos para Edge Layer
============================================================================

Versión simplificada del Edge Server sin dependencias web.
Proporciona una CLI interactiva para todas las operaciones principales.

Características:
    ✓ Discovery de dispositivos Modbus RTU
    ✓ Lectura de identidad y alias
    ✓ Polling manual o automático de telemetría
    ✓ Comando Identify (parpadeo LED)
    ✓ Cambio de alias y UnitID
    ✓ Logs claros y estructurados
    ✓ Salida formateada en terminal

Uso:
    python edge_cli.py              # Modo interactivo
    python edge_cli.py --discover   # Discovery y salir
    python edge_cli.py --poll 2     # Polling del UnitID 2

============================================================================
"""
import sys
import os
import time
import argparse
from datetime import datetime
from typing import Optional, Dict, List

# Añadir src/ al path para importar módulos compartidos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'edge', 'src'))

from modbus_master import ModbusMaster
from device_manager import DeviceManager, Device
from data_normalizer import DataNormalizer
from logger import logger
from config import Config


# ============================================================================
# UTILIDADES DE PRESENTACIÓN
# ============================================================================

class Colors:
    """Códigos ANSI para colorear output en terminal"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str):
    """Imprime encabezado destacado"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_success(text: str):
    """Mensaje de éxito en verde"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """Mensaje de error en rojo"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    """Mensaje de advertencia en amarillo"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text: str):
    """Mensaje informativo en cyan"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def print_device(device: Device):
    """Imprime información de un dispositivo de forma clara"""
    print(f"\n{Colors.BOLD}UnitID {device.unit_id}{Colors.END}")
    print(f"  Vendor:  {device.vendor_str or 'N/A'} (ID: 0x{device.vendor_id:04X})" if device.vendor_id else "  Vendor:  N/A")
    print(f"  Product: {device.product_str or 'N/A'} (ID: 0x{device.product_id:04X})" if device.product_id else "  Product: N/A")
    print(f"  HW:      {device.hw_version or 'N/A'}")
    print(f"  FW:      {device.fw_version or 'N/A'}")
    print(f"  Alias:   {device.alias or '(sin alias)'}")
    
    # Capacidades
    caps = []
    if device.has_mpu:
        caps.append("MPU6050")
    if device.has_wind:
        caps.append("Viento")
    print(f"  Caps:    {', '.join(caps) if caps else 'N/A'}")
    
    # Estado
    status_color = Colors.GREEN if device.status == "online" else Colors.RED
    print(f"  Estado:  {status_color}{device.status}{Colors.END}")
    
    if device.last_seen:
        print(f"  Visto:   {device.last_seen.strftime('%Y-%m-%d %H:%M:%S')}")


def print_telemetry(data: dict):
    """Imprime telemetría de forma legible"""
    unit_id = data.get('unit_id', '?')
    alias = data.get('alias', '')
    timestamp = data.get('timestamp', '')
    
    print(f"\n{Colors.BOLD}Telemetría - UnitID {unit_id}{Colors.END} ({alias})")
    print(f"Timestamp: {timestamp}")
    
    tel = data.get('telemetry', {})
    
    # Ángulos (si existen)
    if 'angle_x_deg' in tel or 'angle_y_deg' in tel:
        print(f"\n  {Colors.CYAN}Inclinación:{Colors.END}")
        if 'angle_x_deg' in tel:
            print(f"    Pitch (X): {tel['angle_x_deg']:7.2f}°")
        if 'angle_y_deg' in tel:
            print(f"    Roll  (Y): {tel['angle_y_deg']:7.2f}°")
    
    # Temperatura
    if 'temperature_c' in tel:
        print(f"\n  {Colors.CYAN}Temperatura:{Colors.END}")
        print(f"    {tel['temperature_c']:6.2f} °C")
    
    # Aceleración
    acc = tel.get('acceleration', {})
    if acc:
        print(f"\n  {Colors.CYAN}Aceleración:{Colors.END}")
        print(f"    X: {acc.get('x_g', 0):7.3f} g")
        print(f"    Y: {acc.get('y_g', 0):7.3f} g")
        print(f"    Z: {acc.get('z_g', 0):7.3f} g")
    
    # Giroscopio
    gyro = tel.get('gyroscope', {})
    if gyro:
        print(f"\n  {Colors.CYAN}Giroscopio:{Colors.END}")
        print(f"    X: {gyro.get('x_dps', 0):7.2f} °/s")
        print(f"    Y: {gyro.get('y_dps', 0):7.2f} °/s")
        print(f"    Z: {gyro.get('z_dps', 0):7.2f} °/s")
    
    # Viento
    wind = tel.get('wind', {})
    if wind:
        print(f"\n  {Colors.CYAN}Viento:{Colors.END}")
        if 'speed_mps' in wind:
            kmh = wind['speed_mps'] * 3.6
            print(f"    Velocidad: {wind['speed_mps']:6.2f} m/s ({kmh:6.2f} km/h)")
        if 'direction_deg' in wind:
            print(f"    Dirección: {wind['direction_deg']:3.0f}°")
    
    # Estadísticas (si existen)
    wind_stats = tel.get('wind_stats', {})
    if wind_stats:
        print(f"\n  {Colors.CYAN}Estadísticas Viento (5s):{Colors.END}")
        if 'min_mps' in wind_stats:
            print(f"    Mín: {wind_stats['min_mps']:6.2f} m/s")
        if 'max_mps' in wind_stats:
            print(f"    Máx: {wind_stats['max_mps']:6.2f} m/s")
        if 'avg_mps' in wind_stats:
            print(f"    Med: {wind_stats['avg_mps']:6.2f} m/s")
    
    # Contador de muestras
    if 'sample_count' in tel:
        print(f"\n  Muestras: {tel['sample_count']}")


# ============================================================================
# CLASE PRINCIPAL CLI
# ============================================================================

class EdgeCLI:
    """Interfaz de línea de comandos para Edge Layer"""
    
    def __init__(self):
        """Inicializa componentes del Edge"""
        print_header("EDGE CLI - Supervisor de Cargas")
        
        print_info(f"Puerto Modbus: {Config.MODBUS_PORT}")
        print_info(f"Baudrate: {Config.MODBUS_BAUDRATE}")
        print_info(f"Timeout: {Config.MODBUS_TIMEOUT}s")
        
        try:
            # Inicializar Modbus Master
            self.modbus = ModbusMaster()
            self.modbus.connect()
            print_success("Modbus Master conectado")
            
            # Normalizer para telemetría (necesario para DeviceManager)
            self.normalizer = DataNormalizer()
            print_success("Data Normalizer listo")
            
            # Inicializar Device Manager (requiere modbus y normalizer)
            self.device_manager = DeviceManager(self.modbus, self.normalizer)
            print_success("Device Manager inicializado")
            
        except Exception as e:
            print_error(f"Error en inicialización: {e}")
            logger.exception("Error fatal en inicialización CLI")
            sys.exit(1)
    
    def discover(self, unit_id_min: int = 1, unit_id_max: int = 10) -> Dict[int, Device]:
        """
        Ejecuta discovery de dispositivos
        
        Args:
            unit_id_min: UnitID mínimo a escanear
            unit_id_max: UnitID máximo a escanear
            
        Returns:
            Diccionario {unit_id: Device} de dispositivos encontrados
        """
        print_header(f"DISCOVERY: UnitID {unit_id_min}..{unit_id_max}")
        
        start_time = time.time()
        devices = self.device_manager.discover_devices(unit_id_min, unit_id_max)
        elapsed = time.time() - start_time
        
        if devices:
            print_success(f"Encontrados {len(devices)} dispositivo(s) en {elapsed:.2f}s")
            for device in devices.values():
                print_device(device)
        else:
            print_warning(f"No se encontraron dispositivos (escaneados en {elapsed:.2f}s)")
        
        return devices
    
    def list_devices(self):
        """Lista dispositivos conocidos en caché"""
        print_header("DISPOSITIVOS EN CACHÉ")
        
        devices = self.device_manager.get_all_devices()
        
        if not devices:
            print_warning("No hay dispositivos en caché. Ejecuta discovery primero.")
            return
        
        print_info(f"Total: {len(devices)} dispositivo(s)")
        
        for device in devices.values():
            print_device(device)
    
    def read_telemetry(self, unit_id: int) -> Optional[dict]:
        """
        Lee telemetría de un dispositivo
        
        Args:
            unit_id: UnitID del dispositivo
            
        Returns:
            Diccionario con telemetría normalizada o None si error
        """
        print_header(f"LECTURA TELEMETRÍA - UnitID {unit_id}")
        
        device = self.device_manager.get_device(unit_id)
        if not device:
            print_error(f"Dispositivo {unit_id} no encontrado. Ejecuta discovery primero.")
            return None
        
        try:
            # Determinar qué registros leer según capacidades
            if device.has_wind and device.has_mpu:
                # Leer todo: base + viento + stats
                addr = 0x0000
                count = 27  # 0x0000-0x001A
            elif device.has_wind:
                # Solo viento
                addr = 0x0009
                count = 9  # 0x0009-0x0011
            else:
                # Solo MPU/base
                addr = 0x0000
                count = 13  # 0x0000-0x000C
            
            print_info(f"Leyendo {count} registros desde 0x{addr:04X}...")
            
            # Leer registros Input
            result = self.modbus.read_input_registers(unit_id, addr, count)
            
            if result is None:
                print_error("Error en lectura Modbus (timeout o excepción)")
                return None
            
            # Normalizar
            telemetry = self.normalizer.normalize_telemetry(
                result, 
                has_wind=device.has_wind,
                has_mpu=device.has_mpu
            )
            
            # Construir payload completo
            data = {
                'unit_id': unit_id,
                'alias': device.alias,
                'timestamp': datetime.now().isoformat(),
                'telemetry': telemetry,
                'status': 'ok'
            }
            
            print_success("Telemetría leída correctamente")
            print_telemetry(data)
            
            return data
            
        except Exception as e:
            print_error(f"Error leyendo telemetría: {e}")
            logger.exception(f"Error en read_telemetry UnitID {unit_id}")
            return None
    
    def poll_continuous(self, unit_id: int, interval: float = 2.0):
        """
        Polling continuo de un dispositivo
        
        Args:
            unit_id: UnitID del dispositivo
            interval: Segundos entre lecturas
        """
        print_header(f"POLLING CONTINUO - UnitID {unit_id}")
        print_info(f"Intervalo: {interval}s")
        print_info("Presiona Ctrl+C para detener\n")
        
        try:
            count = 0
            while True:
                count += 1
                print(f"\n{Colors.BOLD}--- Lectura #{count} ---{Colors.END}")
                
                data = self.read_telemetry(unit_id)
                
                if data is None:
                    print_warning("Reintentando en próximo ciclo...")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Polling detenido por usuario{Colors.END}")
            print_info(f"Total de lecturas: {count}")
    
    def identify_device(self, unit_id: int, duration: int = 10):
        """
        Activa LED identify en dispositivo
        
        Args:
            unit_id: UnitID del dispositivo
            duration: Duración del parpadeo en segundos
        """
        print_header(f"IDENTIFY - UnitID {unit_id}")
        print_info(f"Duración: {duration}s")
        
        success = self.device_manager.identify_device(unit_id, duration)
        
        if success:
            print_success(f"Comando identify enviado. LED parpadeando por {duration}s")
        else:
            print_error("Error enviando comando identify")
    
    def set_alias(self, unit_id: int, alias: str):
        """
        Cambia alias de un dispositivo
        
        Args:
            unit_id: UnitID del dispositivo
            alias: Nuevo alias (máx 64 caracteres ASCII)
        """
        print_header(f"CAMBIAR ALIAS - UnitID {unit_id}")
        print_info(f"Nuevo alias: '{alias}'")
        
        success = self.device_manager.set_device_alias(unit_id, alias)
        
        if success:
            print_success(f"Alias guardado en EEPROM: '{alias}'")
            # Actualizar dispositivo en caché
            device = self.device_manager.get_device(unit_id)
            if device:
                device.alias = alias
        else:
            print_error("Error guardando alias")
    
    def change_unit_id(self, old_unit_id: int, new_unit_id: int):
        """
        Cambia UnitID de un dispositivo
        
        Args:
            old_unit_id: UnitID actual
            new_unit_id: Nuevo UnitID (1-247)
        """
        print_header(f"CAMBIAR UNIT ID: {old_unit_id} → {new_unit_id}")
        
        if not (1 <= new_unit_id <= 247):
            print_error("UnitID debe estar en rango 1-247")
            return
        
        # Verificar que no exista conflicto
        if self.device_manager.get_device(new_unit_id):
            print_error(f"Ya existe un dispositivo con UnitID {new_unit_id}")
            return
        
        print_warning("⚠️  ADVERTENCIA: Esto cambiará la dirección Modbus del dispositivo")
        confirm = input(f"¿Confirmar cambio {old_unit_id} → {new_unit_id}? (s/N): ")
        
        if confirm.lower() != 's':
            print_info("Operación cancelada")
            return
        
        success = self.device_manager.change_device_unit_id(old_unit_id, new_unit_id)
        
        if success:
            print_success(f"UnitID cambiado: {old_unit_id} → {new_unit_id}")
            print_info("El dispositivo ahora responderá en el nuevo UnitID")
            print_info("Recomendado: Ejecuta discovery para verificar")
        else:
            print_error("Error cambiando UnitID")
    
    def show_menu(self):
        """Muestra menú interactivo"""
        print_header("MENÚ PRINCIPAL")
        
        options = [
            ("1", "Discovery de dispositivos"),
            ("2", "Listar dispositivos en caché"),
            ("3", "Leer telemetría (una vez)"),
            ("4", "Polling continuo"),
            ("5", "Identify (parpadeo LED)"),
            ("6", "Cambiar alias"),
            ("7", "Cambiar UnitID"),
            ("8", "Mostrar este menú"),
            ("0", "Salir"),
        ]
        
        for key, desc in options:
            print(f"  {Colors.BOLD}{key}{Colors.END} - {desc}")
        print()
    
    def run_interactive(self):
        """Modo interactivo con menú"""
        self.show_menu()
        
        while True:
            try:
                choice = input(f"\n{Colors.BOLD}Opción > {Colors.END}").strip()
                
                if choice == '0':
                    print_info("Saliendo...")
                    break
                
                elif choice == '1':
                    # Discovery
                    min_id = int(input("UnitID mínimo (1): ") or "1")
                    max_id = int(input("UnitID máximo (10): ") or "10")
                    self.discover(min_id, max_id)
                
                elif choice == '2':
                    # Listar
                    self.list_devices()
                
                elif choice == '3':
                    # Leer telemetría
                    unit_id = int(input("UnitID: "))
                    self.read_telemetry(unit_id)
                
                elif choice == '4':
                    # Polling continuo
                    unit_id = int(input("UnitID: "))
                    interval = float(input("Intervalo (s) [2.0]: ") or "2.0")
                    self.poll_continuous(unit_id, interval)
                
                elif choice == '5':
                    # Identify
                    unit_id = int(input("UnitID: "))
                    duration = int(input("Duración (s) [10]: ") or "10")
                    self.identify_device(unit_id, duration)
                
                elif choice == '6':
                    # Cambiar alias
                    unit_id = int(input("UnitID: "))
                    alias = input("Nuevo alias: ").strip()
                    self.set_alias(unit_id, alias)
                
                elif choice == '7':
                    # Cambiar UnitID
                    old = int(input("UnitID actual: "))
                    new = int(input("Nuevo UnitID: "))
                    self.change_unit_id(old, new)
                
                elif choice == '8':
                    # Mostrar menú
                    self.show_menu()
                
                else:
                    print_warning("Opción no válida")
                    
            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Operación cancelada{Colors.END}")
                continue
            except ValueError as e:
                print_error(f"Entrada inválida: {e}")
            except Exception as e:
                print_error(f"Error: {e}")
                logger.exception("Error en menú interactivo")
    
    def cleanup(self):
        """Limpieza al salir"""
        print_info("\nCerrando conexiones...")
        try:
            if hasattr(self, 'modbus'):
                self.modbus.disconnect()
                print_success("Modbus desconectado")
        except Exception as e:
            logger.warning(f"Error en cleanup: {e}")


# ============================================================================
# MAIN - Punto de entrada
# ============================================================================

def main():
    """Punto de entrada principal"""
    parser = argparse.ArgumentParser(
        description="Edge CLI - Interfaz de línea de comandos para Modbus RTU",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python edge_cli.py                    # Modo interactivo (recomendado)
  python edge_cli.py --discover         # Discovery rápido 1-10
  python edge_cli.py --discover 1 20    # Discovery 1-20
  python edge_cli.py --poll 2           # Polling UnitID 2
  python edge_cli.py --poll 2 --interval 5  # Polling cada 5s
  python edge_cli.py --identify 2 --duration 15  # Identify 15s
        """
    )
    
    # Argumentos
    parser.add_argument('--discover', nargs='*', metavar=('MIN', 'MAX'),
                        help='Discovery de dispositivos (opcional: min max)')
    parser.add_argument('--poll', type=int, metavar='UNIT_ID',
                        help='Polling continuo de un dispositivo')
    parser.add_argument('--interval', type=float, default=2.0,
                        help='Intervalo de polling en segundos (default: 2.0)')
    parser.add_argument('--identify', type=int, metavar='UNIT_ID',
                        help='Enviar comando identify a dispositivo')
    parser.add_argument('--duration', type=int, default=10,
                        help='Duración de identify en segundos (default: 10)')
    parser.add_argument('--list', action='store_true',
                        help='Listar dispositivos en caché')
    parser.add_argument('--keep-connected', action='store_true',
                        help='Mantener conexión abierta después de comando (útil para testing)')
    
    args = parser.parse_args()
    
    # Crear CLI
    cli = EdgeCLI()
    
    try:
        # Modos no interactivos
        if args.discover is not None:
            # Discovery
            if len(args.discover) == 0:
                cli.discover(1, 10)
            elif len(args.discover) == 2:
                min_id = int(args.discover[0])
                max_id = int(args.discover[1])
                cli.discover(min_id, max_id)
            else:
                print_error("Uso: --discover [min max]")
            
            # Ofrecer continuar al modo interactivo
            if not args.keep_connected:
                devices = cli.device_manager.get_all_devices()
                
                print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
                if devices:
                    print(f"{Colors.GREEN}Se encontraron {len(devices)} dispositivo(s){Colors.END}")
                    print(f"\n{Colors.CYAN}Opciones:{Colors.END}")
                else:
                    print(f"{Colors.YELLOW}No se encontraron dispositivos{Colors.END}")
                    print(f"\n{Colors.CYAN}Puede:{Colors.END}")
                
                print(f"  1 - Entrar al menú interactivo completo")
                print(f"  2 - Intentar discovery de nuevo")
                print(f"  0 - Salir")
                
                try:
                    choice = input(f"\n{Colors.BOLD}Opción > {Colors.END}").strip()
                    
                    if choice == '1':
                        # Ir al menú interactivo
                        cli.run_interactive()
                    elif choice == '2':
                        # Repetir discovery
                        min_id = int(input("UnitID mínimo [1]: ") or "1")
                        max_id = int(input("UnitID máximo [10]: ") or "10")
                        cli.discover(min_id, max_id)
                        # Después de este discovery, entrar al menú
                        print(f"\n{Colors.CYAN}Entrando al menú interactivo...{Colors.END}")
                        cli.run_interactive()
                    elif choice == '0':
                        print_info("Saliendo...")
                    else:
                        print_warning("Opción no válida, saliendo...")
                except (ValueError, KeyboardInterrupt):
                    print(f"\n{Colors.YELLOW}Operación cancelada{Colors.END}")
        
        elif args.poll:
            # Polling continuo
            cli.poll_continuous(args.poll, args.interval)
        
        elif args.identify:
            # Identify
            cli.identify_device(args.identify, args.duration)
        
        elif args.list:
            # Listar
            cli.list_devices()
        
        else:
            # Modo interactivo (default)
            cli.run_interactive()
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Programa interrumpido por usuario{Colors.END}")
    
    finally:
        cli.cleanup()


if __name__ == '__main__':
    main()
