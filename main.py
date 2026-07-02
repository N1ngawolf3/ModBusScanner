import minimalmodbus
import serial
import time

# Параметры сканирования
PORT = 'COM6'                     # Ваш порт
BAUDRATES = [9600, 19200, 38400, 57600, 115200]
SLAVE_IDS = range(1, 10)         # 1–247
TIMEOUT = 0.5                     # секунд


def scan_modbus_rtu(port, baudrates, slave_ids, timeout):
    print(f"Начинаю сканирование порта {port}...")
    found_devices = []

    for baudrate in baudrates:
        print(f"\n--- Проверка скорости: {baudrate} бод ---")

        for slave_id in slave_ids:
            # Создаём инструмент для каждого сочетания
            instrument = minimalmodbus.Instrument(port, slave_id)
            instrument.serial.baudrate = baudrate
            instrument.serial.timeout = timeout
            instrument.serial.bytesize = 8
            instrument.serial.parity = serial.PARITY_NONE   # 'N'
            instrument.serial.stopbits = 1
            instrument.mode = 'rtu'   # Режим RTU

            try:
                # Пытаемся прочитать один holding register по адресу 0
                value = instrument.read_register(0, 0)  # адрес 0, без десятичных знаков
                # Если дошли сюда – ответ получен без ошибки
                print(f"  >>> УСТРОЙСТВО НАЙДЕНО! Скорость: {baudrate}, Адрес: {slave_id}")
                found_devices.append({'baudrate': baudrate, 'slave_id': slave_id})
            except (serial.SerialException, minimalmodbus.ModbusException, IOError):
                # Таймаут или ошибка Modbus – просто игнорируем
                print(f"Нет связи. Скорость: {baudrate}, Адрес: {slave_id}")
                pass
            except Exception as e:
                # Другие неожиданные ошибки
                print(f"  Ошибка при опросе адреса {slave_id}: {e}")

    # Вывод результатов
    print("\n" + "="*40)
    if found_devices:
        print("Сканирование завершено. Найдены устройства:")
        for device in found_devices:
            print(f"  - Скорость: {device['baudrate']}, Адрес: {device['slave_id']}")
    else:
        print("Устройства не найдены. Попробуйте расширить диапазон скоростей или адресов.")
    print("="*40)


if __name__ == "__main__":
    start = time.time()
    scan_modbus_rtu(PORT, BAUDRATES, SLAVE_IDS, TIMEOUT)
    end = time.time()
    print(f'Время выполнения: {round(end-start, 3)}')