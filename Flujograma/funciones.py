from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QToolButton, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QMessageBox,
                             QPushButton, QInputDialog, QDialog, QDialogButtonBox, QProgressBar, QFormLayout,
                             QTableWidget, QTableWidgetItem)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QColor
import pymysql
import sys
import os
import time
import sqlite3

# Constantes para la conexión a la base de datos
DB_CONFIG = {
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "db": "pruebadedatos",
    "host": "servicioalochoro-prueba1631.l.aivencloud.com",
    "password": "AVNS_XIL6StsPZSOwo0ZxNfr",
    "port": 15140,
    "user": "avnadmin",
}

def resource_path(relative_path):
    """Obtiene la ruta absoluta del recurso, funciona para desarrollo y PyInstaller"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class WorkerSignals(QObject):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

class WorkerThread(QThread):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.function(self.signals.progress, *self.args, **self.kwargs)
            self.signals.finished.emit(True, "Operación completada con éxito")
        except Exception as e:
            self.signals.finished.emit(False, str(e))

class DatabaseManager:
    @staticmethod
    def execute_query(query, params=None):
        with pymysql.connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                connection.commit()

    @staticmethod
    def get_last_id():
        result = DatabaseManager.execute_query("SELECT MAX(id) as max_id FROM mamabichosricos")
        return result[0]['max_id'] if result else 0

    @staticmethod
    def reordenar_ids(progress_callback):
        try:
            registros = DatabaseManager.execute_query("SELECT * FROM mamabichosricos ORDER BY id")
            total = len(registros)
            for i, registro in enumerate(registros, start=1):
                DatabaseManager.execute_query(
                    "UPDATE mamabichosricos SET id = %s WHERE id = %s",
                    (i, registro['id'])
                )
                # Simulamos un proceso más largo para ver la barra de progreso
                time.sleep(0.1)
                # Emitimos el progreso
                progress_callback.emit(int((i / total) * 100))
            return True
        except Exception as e:
            print(f"Error al reordenar IDs: {str(e)}")
            return False

class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="Progreso", description="Procesando..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(300, 100)
        layout = QVBoxLayout(self)
        
        self.description_label = QLabel(description)
        layout.addWidget(self.description_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(True)

    def set_range(self, minimum, maximum):
        self.progress_bar.setRange(minimum, maximum)

    def set_value(self, value):
        self.progress_bar.setValue(value)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.worker = None
        self.progress_dialog = None

    def init_ui(self):
        self.setWindowTitle("Interfaz de Mamabichosricos")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon(resource_path("image.jpeg")))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        main_layout.addWidget(left_widget)

        # Creamos los botones "Agregar Datos", "Consultar Datos", "Eliminar Datos", "Modificar Datos" y "Reordenar IDs"
        buttons_config = [
            ("Agregar Datos", self.agregar_datos, "add_icon.png"),
            ("Consultar Datos", self.consultar_datos, "search_icon.png"),
            ("Eliminar Datos", self.eliminar_datos, "delete_icon.png"),
            ("Modificar Datos", self.modificar_datos, "edit_icon.png"),
            ("Reordenar IDs", self.reordenar_ids, "reorder_icon.png"),
        ]
        
        for button_text, slot, icon_name in buttons_config:
            self.create_tool_button(button_text, slot, icon_name, left_layout)

        left_layout.addStretch()

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        main_layout.addWidget(right_widget)

        # Agregar barra de búsqueda en el lado derecho
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar...")
        self.search_bar.textChanged.connect(self.filter_tree_widget)
        right_layout.addWidget(self.search_bar)

        # Agregar el QTreeWidget al lado derecho
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["ID", "Nombre", "Nivel de mamador"])
        right_layout.addWidget(self.tree_widget)

        # Agregar barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

    def create_tool_button(self, text, slot, icon_name, layout):
        button = QToolButton()
        button.setText(text)
        button.setIcon(QIcon(resource_path(icon_name)))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIconSize(QSize(32, 32))
        button.clicked.connect(slot)
        button.setFixedSize(100, 80)
        button.setObjectName(text)  # Asignamos un nombre al botón
        layout.addWidget(button)

    def run_with_progress(self, function, *args, **kwargs):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = WorkerThread(function, *args, **kwargs)
        self.worker.signals.finished.connect(self.on_worker_finished)
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.start()

    def on_worker_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.mostrar_mensaje("Éxito" if success else "Error", message, 
                             QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical)
        self.consultar_datos()
        self.worker.quit()
        self.worker.wait()
        self.worker = None

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def mostrar_mensaje(self, titulo, mensaje, icono=QMessageBox.Icon.Information):
        msg_box = QMessageBox(self)
        msg_box.setIcon(icono)
        msg_box.setText(mensaje)
        msg_box.setWindowTitle(titulo)
        msg_box.setWindowIcon(QIcon(resource_path("image.jpeg")))
        msg_box.exec()

    def agregar_datos(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Agregar Datos")
        layout = QVBoxLayout(dialog)

        nombre_layout = QHBoxLayout()
        nombre_label = QLabel("Nombre:")
        nombre_input = QLineEdit()
        nombre_layout.addWidget(nombre_label)
        nombre_layout.addWidget(nombre_input)

        nivel_layout = QHBoxLayout()
        nivel_label = QLabel("Nivel de mamador:")
        nivel_mamador_input = QLineEdit()
        nivel_layout.addWidget(nivel_label)
        nivel_layout.addWidget(nivel_mamador_input)

        layout.addLayout(nombre_layout)
        layout.addLayout(nivel_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        # Conectar la señal returnPressed de los QLineEdit al método accept del diálogo
        nombre_input.returnPressed.connect(dialog.accept)
        nivel_mamador_input.returnPressed.connect(dialog.accept)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            nombre = nombre_input.text()
            nivel_mamador = nivel_mamador_input.text()

            try:
                # Obtener el siguiente ID disponible
                new_id = DatabaseManager.get_last_id() + 1
                
                # Insertar los nuevos datos en la base de datos
                DatabaseManager.execute_query(
                    "INSERT INTO mamabichosricos(id, nombre, niveldemamador) VALUES(%s, %s, %s)",
                    (new_id, nombre, nivel_mamador)
                )
                
                self.mostrar_mensaje("Éxito", f"Datos agregados exitosamente con ID: {new_id}")
                self.consultar_datos()  # Actualizar la vista
            except Exception as e:
                self.mostrar_mensaje("Error", f"No se pudo agregar el registro: {str(e)}", QMessageBox.Icon.Critical)

    def guardar_datos_seguro(self):
        try:
            data = {key: entry.text() for key, entry in self.entries.items()}
            if not all(data.values()):
                raise ValueError("Todos los campos deben estar llenos")
            
            new_id = DatabaseManager.get_last_id() + 1
            
            DatabaseManager.execute_query(
                "INSERT INTO mamabichosricos(id, nombre, niveldemamador) VALUES(%s, %s, %s)",
                (new_id, data['nombre'], data['nivel de mamador'])
            )
            
            for entry in self.entries.values():
                entry.clear()
            
            self.mostrar_mensaje("Éxito", f"Datos agregados exitosamente con ID: {new_id}")
        except ValueError as e:
            self.mostrar_mensaje("Error de validación", str(e), QMessageBox.Icon.Warning)
        except Exception as e:
            self.mostrar_mensaje("Error inesperado", f"Ocurrió un error al guardar los datos: {str(e)}", QMessageBox.Icon.Critical)

    def consultar_datos(self):
        self.progress_dialog = ProgressDialog(self, title="Consulta de Datos", description="Consultando datos...")
        self.progress_dialog.set_range(0, 100)
        self.progress_dialog.show()

        self.worker = WorkerThread(self.realizar_consulta)
        self.worker.signals.finished.connect(self.on_consulta_finished)
        self.worker.signals.progress.connect(self.progress_dialog.set_value)
        self.worker.start()

    def realizar_consulta(self, progress_callback):
        try:
            # Obtener el total de registros para configurar la barra de progreso
            total_registros = DatabaseManager.execute_query("SELECT COUNT(*) as total FROM mamabichosricos")[0]['total']
            
            # Ejecutar la consulta
            resultados = DatabaseManager.execute_query("SELECT * FROM mamabichosricos")
            
            # Limpiar el árbol antes de agregar nuevos datos
            self.tree_widget.clear()
            
            # Simular un proceso más largo
            total_steps = max(100, total_registros)  # Asegurar al menos 100 pasos
            
            # Agregar los resultados al árbol
            for i, registro in enumerate(resultados):
                item = QTreeWidgetItem(self.tree_widget)
                item.setText(0, str(registro['id']))
                item.setText(1, registro['nombre'])
                item.setText(2, str(registro['niveldemamador']))
                
                # Calcular el progreso
                progress = int(((i + 1) / total_registros) * 100)
                
                # Actualizar la barra de progreso
                progress_callback.emit(progress)
                
                # Simular un proceso más largo
                time.sleep(0.01)  # Añadir un pequeño retraso
            
            # Asegurar que la barra llegue al 100%
            progress_callback.emit(100)
            
            return True, f"Se consultaron {total_registros} registros exitosamente"
        except Exception as e:
            print(f"Error detallado: {e}")  # Imprimir el error detallado en la consola
            return False, f"No se pudieron consultar los datos: {str(e)}"

    def on_consulta_finished(self, success, message):
        self.progress_dialog.close()
        self.progress_dialog = None
        self.mostrar_mensaje("Éxito" if success else "Error", message, 
                             QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical)
        self.worker.quit()
        self.worker.wait()
        self.worker = None

    def eliminar_datos(self):
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            self.mostrar_mensaje("Error", "Por favor, seleccione un registro para eliminar", QMessageBox.Icon.Warning)
            return

        item = selected_items[0]
        id_to_delete = item.text(0)  # Asumimos que el ID está en la primera columna

        confirm = QMessageBox.question(self, "Confirmar eliminación", 
                                       f"¿Está seguro de que desea eliminar el registro con ID {id_to_delete}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                DatabaseManager.execute_query("DELETE FROM mamabichosricos WHERE id = %s", (id_to_delete,))
                self.mostrar_mensaje("Éxito", f"Registro con ID {id_to_delete} eliminado exitosamente")
                self.consultar_datos()  # Actualizamos la vista después de eliminar
            except Exception as e:
                self.mostrar_mensaje("Error", f"No se pudo eliminar el registro: {str(e)}", QMessageBox.Icon.Critical)

    def modificar_datos(self):
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            self.mostrar_mensaje("Error", "Por favor, seleccione un registro para modificar", QMessageBox.Icon.Warning)
            return

        item = selected_items[0]
        id_to_modify = item.text(0)
        nombre_actual = item.text(1)
        nivel_actual = item.text(2)

        # Crear una ventana de diálogo para ingresar los nuevos datos
        dialog = QDialog(self)
        dialog.setWindowTitle("Modificar Datos")
        dialog.setWindowIcon(QIcon(resource_path("image.jpeg")))
        layout = QVBoxLayout(dialog)

        nombre_layout = QHBoxLayout()
        nombre_label = QLabel("Nombre:")
        nombre_input = QLineEdit(nombre_actual)
        nombre_layout.addWidget(nombre_label)
        nombre_layout.addWidget(nombre_input)

        nivel_layout = QHBoxLayout()
        nivel_label = QLabel("Nivel de mamador:")
        nivel_input = QLineEdit(nivel_actual)
        nivel_layout.addWidget(nivel_label)
        nivel_layout.addWidget(nivel_input)

        layout.addLayout(nombre_layout)
        layout.addLayout(nivel_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Conectar la señal returnPressed de los QLineEdit al método accept del diálogo
        nombre_input.returnPressed.connect(dialog.accept)
        nivel_input.returnPressed.connect(dialog.accept)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            nuevo_nombre = nombre_input.text()
            nuevo_nivel = nivel_input.text()

            try:
                DatabaseManager.execute_query(
                    "UPDATE mamabichosricos SET nombre = %s, niveldemamador = %s WHERE id = %s",
                    (nuevo_nombre, nuevo_nivel, id_to_modify)
                )
                self.mostrar_mensaje("Éxito", f"Registro con ID {id_to_modify} modificado exitosamente")
                self.consultar_datos()  # Actualizamos la vista después de modificar
            except Exception as e:
                self.mostrar_mensaje("Error", f"No se pudo modificar el registro: {str(e)}", QMessageBox.Icon.Critical)

    def reordenar_ids(self):
        confirm = QMessageBox.question(self, "Confirmar reordenación", 
                                       "¿Está seguro de que desea reordenar los IDs? Esta acción no se puede deshacer.",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.progress_dialog = ProgressDialog(self, title="Reordenación de IDs", description="Reordenando IDs...")
            self.progress_dialog.set_range(0, 100)
            self.progress_dialog.show()

            self.worker = WorkerThread(DatabaseManager.reordenar_ids)
            self.worker.signals.finished.connect(self.on_reordenar_finished)
            self.worker.signals.progress.connect(self.progress_dialog.set_value)
            self.worker.start()

    def on_reordenar_finished(self, success, message):
        self.progress_dialog.close()
        self.progress_dialog = None
        self.mostrar_mensaje("Éxito" if success else "Error", message, 
                             QMessageBox.Icon.Information if success else QMessageBox.Icon.Critical)
        
        # Actualizar los datos sin mostrar la barra de progreso
        self.actualizar_datos_sin_progreso()
        
        self.worker.quit()
        self.worker.wait()
        self.worker = None

    def actualizar_datos_sin_progreso(self):
        try:
            resultados = DatabaseManager.execute_query("SELECT * FROM mamabichosricos")
            self.tree_widget.clear()
            for registro in resultados:
                item = QTreeWidgetItem(self.tree_widget)
                item.setText(0, str(registro['id']))
                item.setText(1, registro['nombre'])
                item.setText(2, str(registro['niveldemamador']))
        except Exception as e:
            self.mostrar_mensaje("Error", f"No se pudieron actualizar los datos: {str(e)}", QMessageBox.Icon.Critical)

    def closeEvent(self, event):
        if self.worker:
            self.worker.quit()
            self.worker.wait()
        event.accept()

    def filter_tree_widget(self, text):
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            should_show = any(text.lower() in item.text(j).lower() for j in range(item.columnCount()))
            item.setHidden(not should_show)

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("image.jpeg")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()