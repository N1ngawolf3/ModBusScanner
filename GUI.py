import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.uic import loadUi
import minimalmodbus
from PyQt6.QtCore import QThread
import serial.tools.list_ports
import serial
from main import scan_modbus_rtu
import time
import traceback
from PyQt6.QtCore import QObject, pyqtSignal


def global_exception_handler(exc_type, exc_value, exc_tb):
    #запись в логи
    error_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    app = QApplication.instance()
    if app:
        # Находим главное окно (предполагаем, что оно одно)
        main_window = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                main_window = widget
                break
        QMessageBox.critical(
            main_window,
            "Ошибка",
            f"Программа столкнулась ошибкой.\n"
            f"{error_text}"
        )


class ModbusScanner(QObject):
    # Сигнал для отправки текстовых сообщений в GUI
    message_signal = pyqtSignal(str)
    # Сигнал о завершении работы
    progress_signal = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, port, baudrates, slave_ids, timeout=0.5, bytesize=8, parity = serial.PARITY_NONE, stopbits=1):
        super().__init__()
        self.port = port
        self.baudrates = baudrates
        self.slave_ids = slave_ids
        self.timeout = timeout
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self._is_running = True  # флаг для возможности остановки

    def stop(self):
        """Метод для остановки сканирования"""
        self._is_running = False

    def scan(self):
        """Основная рабочая функция. Выполняется в потоке."""
        total = len(self.baudrates) * len(self.slave_ids)
        current = 0
        self.message_signal.emit(f"Сканирование порта {self.port}...")
        found_devices = []

        for baudrate in self.baudrates:
            if not self._is_running:
                break
            self.message_signal.emit(f"--- Проверка скорости: {baudrate} бод ---")

            for slave_id in self.slave_ids:
                if not self._is_running:
                    break

                instrument = minimalmodbus.Instrument(self.port, slave_id)
                instrument.serial.baudrate = baudrate
                instrument.serial.timeout = self.timeout
                instrument.serial.bytesize = self.bytesize
                instrument.serial.parity = self.parity
                instrument.serial.stopbits = self.stopbits
                instrument.mode = 'rtu'

                try:
                    # Пробуем прочитать регистр
                    instrument.read_register(0, 0)
                    msg = f">>> УСТРОЙСТВО НАЙДЕНО! Скорость: {baudrate}, Адрес: {slave_id}"
                    self.message_signal.emit(msg)
                    found_devices.append((baudrate, slave_id))
                except Exception:
                    # Таймаут или ошибка — молча пропускаем
                    pass

                current += 1
                percent = int((current / total) * 100)
                self.progress_signal.emit(percent)

        # Итоговое сообщение
        if found_devices:
            self.message_signal.emit("Найдены устройства:")
            for baud, addr in found_devices:
                self.message_signal.emit(f"  - {baud} бод, адрес {addr}")
        else:
            self.message_signal.emit("Ничего не найдено.")

        self.finished.emit()  # сигнализируем об окончании



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        loadUi('Window.ui', self)

        self.comboBox_COM.addItems(port.device for port in serial.tools.list_ports.comports())
        self.pushButton_updateCOM.clicked.connect(self.updateCOM)
        self.executeButton.clicked.connect(self.execute)
        self.baud_checkboxes_list = [self.checkBox_baud1200, self.checkBox_baud2400, self.checkBox_baud4800,
                                self.checkBox_baud9600, self.checkBox_baud19200, self.checkBox_baud38400,
                                self.checkBox_baud57600,self.checkBox_baud115200]
        self.bytesize_checkboxes_list = [self.checkBox_bit4, self.checkBox_bit5,self.checkBox_bit6,
                                         self.checkBox_bit7, self.checkBox_bit8]
        self.stopbits_checkboxes_list = [self.checkBox_stop1,self.checkBox_stop15,self.checkBox_stop2 ]
        self.progressBar.setVisible(False)

        # Храним ссылки на поток и работника, чтобы не дать сборщику мусора их удалить
        self.thread = None
        self.worker = None

    def updateCOM(self):
        self.comboBox_COM.clear()
        self.comboBox_COM.addItems(port.device for port in serial.tools.list_ports.comports())


    def execute(self):
        self.executeButton.setEnabled(False)
        self.list_widget.clear()
        self.progressBar.setVisible(True)
        port = self.comboBox_COM.currentText()
        start_address = self.spinBox_StartAddress.value()
        end_address = self.spinBox_EndAddress.value()
        timeout = self.spinBox_timeout.value() / 1000
        # Создаём поток
        self.thread = QThread()

        # Создаём работника
        self.worker = ModbusScanner(
            port=port,
            baudrates=[item.text() for item in self.baud_checkboxes_list if item.isChecked()],
            slave_ids=range(start_address, end_address),
            timeout=timeout
            #bytesize=[item.text() for item in self.bytesize_checkboxes_list if item.isChecked()],
            #stopbits=[item.text() for item in self.stopbits_checkboxes_list if item.isChecked()]
        )

        # Перемещаем работника в поток
        self.worker.moveToThread(self.thread)

        # Подключаем сигналы
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.message_signal.connect(self.append_message)
        self.worker.finished.connect(self.scan_finished)
        # При запуске потока вызываем метод scan() работника
        self.thread.started.connect(self.worker.scan)

        # Освобождаем ресурсы после завершения
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Запускаем поток
        self.thread.start()

    def append_message(self, text):
        """Обновление списка в главном потоке"""
        self.list_widget.addItem(text)
        self.list_widget.scrollToBottom()

    def scan_finished(self):
        """Действия после завершения сканирования"""
        self.executeButton.setEnabled(True)
        self.list_widget.addItem("--- Сканирование завершено ---")
        self.progressBar.setVisible(False)

    def update_progress(self, value):
        self.progressBar.setValue(value)





if __name__ == "__main__":
    sys.excepthook = global_exception_handler
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())