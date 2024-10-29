from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QToolButton, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QMessageBox,
                             QPushButton, QInputDialog, QDialog, QDialogButtonBox, QProgressBar, QFormLayout,
                             QTableWidget, QTableWidgetItem, QComboBox, QFrame, QCalendarWidget)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QDate
from PyQt6.QtGui import QIcon, QColor, QPixmap
import pymysql
import sys
import os
import time
import sqlite3
import hashlib
# Constantes para la conexión a la base de datos
DB_CONFIG = {
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "db": "FLUJOGRAMA",
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
        result = DatabaseManager.execute_query("SELECT MAX(id) as max_id FROM documento")
        return result[0]['max_id'] if result else 0
    @staticmethod
    def reordenar_ids(progress_callback):
        try:
            registros = DatabaseManager.execute_query("SELECT * FROM documento ORDER BY id")
            total = len(registros)
            for i, registro in enumerate(registros, start=1):
                DatabaseManager.execute_query(
                    "UPDATE documento SET id = %s WHERE id = %s",
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

    @staticmethod
    def init_user_table():
        query = """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        DatabaseManager.execute_query(query)

    @staticmethod
    def register_user(username, password, email):
        query = """
        INSERT INTO usuarios (username, password, email)
        VALUES (%s, %s, %s)
        """
        DatabaseManager.execute_query(query, (username, password, email))

    @staticmethod
    def validate_login(username, password):
        query = """
        SELECT * FROM usuarios 
        WHERE username = %s AND password = %s
        """
        result = DatabaseManager.execute_query(query, (username, password))
        return len(result) > 0

    @staticmethod
    def generate_salt():
        return os.urandom(32).hex()

    @staticmethod
    def hash_password(password, salt):
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @staticmethod
    def register_user(nombreusuario, password, rol="usuario"):
        try:
            salt = DatabaseManager.generate_salt()
            password_hash = DatabaseManager.hash_password(password, salt)
            
            query = """
            INSERT INTO usuario (nombreusuario, rol, password_hash, salt)
            VALUES (%s, %s, %s, %s)
            """
            DatabaseManager.execute_query(query, (nombreusuario, rol, password_hash, salt))
            return True
        except Exception as e:
            raise Exception(f"Error al registrar usuario: {str(e)}")

    @staticmethod
    def validate_login(nombreusuario, password):
        query = """
        SELECT password_hash, salt, rol 
        FROM usuario 
        WHERE nombreusuario = %s
        """
        result = DatabaseManager.execute_query(query, (nombreusuario,))
        
        if result:
            user = result[0]
            password_hash = DatabaseManager.hash_password(password, user['salt'])
            if password_hash == user['password_hash']:
                return True, user['rol']
        return False, None

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
    def __init__(self, username="", user_role=""):
        super().__init__()
        self.username = username
        self.user_role = user_role
        self.init_ui()
        self.setup_user_info()
        self.worker = None
        self.progress_dialog = None

    def setup_user_info(self):
        """Configura o actualiza la información del usuario"""
        # Buscar el widget contenedor existente y eliminarlo si existe
        existing_user_info = self.findChild(QWidget, "user_info_widget")
        if existing_user_info:
            existing_user_info.deleteLater()

        # Crear nuevo widget contenedor para la información de usuario y botón de cierre
        user_info_widget = QWidget()
        user_info_widget.setObjectName("user_info_widget")
        user_info_layout = QHBoxLayout(user_info_widget)
        user_info_layout.setContentsMargins(5, 5, 5, 5)
        
        # Etiqueta de información de usuario
        user_info_label = QLabel(f"Sesion: {self.username} | Rol: {self.user_role}")
        user_info_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                padding: 5px;
                background-color: #363636;
                border-radius: 3px;
            }
        """)
        # Botón de cerrar sesión
        logout_button = QPushButton("Cerrar Sesión")
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
            }6
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        logout_button.clicked.connect(self.logout)
        
        user_info_layout.addWidget(user_info_label)
        user_info_layout.addWidget(logout_button)
        user_info_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        # Añadir al layout principal
    def init_ui(self):
        self.setWindowTitle("Interfaz de Corporación Isla de Maipo")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon(resource_path("isla_de_maipo.png")))
        # Aplicar estilo oscuro
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTreeWidget {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QTreeWidget::item {
                color: #ffffff;
                background-color: #363636;
            }
            QTreeWidget::item:selected {
                background-color: #4a4a4a;
            }
            QTreeWidget QHeaderView::section {
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #555555;
            }
            QTreeWidget::branch {
                background-color: #363636;
                color: #ffffff;
            }
            QTreeWidget::branch:selected {
                background-color: #4a4a4a;
            }
            QTableWidget {
                background-color: #363636;
                color: #ffffff;
                gridline-color: #555555;
            }
            QTableWidget QHeaderView::section {
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #555555;
            }
            QTableWidget::item {
                color: #ffffff;
                background-color: #363636;
            }
            QTableWidget::item:selected {
                background-color: #4a4a4a;
            }
            QLineEdit {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
            }
            QToolButton {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 5px;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
            }
            QComboBox {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                background-color: #555555;
            }
            QComboBox QAbstractItemView {
                background-color: #363636;
                color: #ffffff;
                selection-background-color: #4a4a4a;
            }
        """)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        main_layout.addWidget(left_widget)

        # Agregar logo y título
        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        scaled_pixmap = logo_pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(logo_label)

        # Agregar título corporativo
        title_label = QLabel("Corporación de Isla de Maipo")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                margin: 10px 0;
            }
        """)
        left_layout.addWidget(title_label)
        # Agregar separador visual
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #555555;")
        left_layout.addWidget(separator)

        # Creamos los botones "Agregar Datos", "Consultar Datos", "Eliminar Datos", "Modificar Datos" y "Reordenar IDs"
        buttons_config = [
            ("Agregar Datos", self.agregar_datos, "add_icon.png"),
            ("Consultar Datos", self.consultar_datos, "search_icon.png"),
            ("Eliminar Datos", self.eliminar_datos, "delete_icon.png"),
            ("Modificar Datos", self.modificar_datos, "edit_icon.png"),
            ("Administrar", self.show_admin_panel, "admin_icon.png"),
        ]
        for button_text, slot, icon_name in buttons_config:
            self.create_tool_button(button_text, slot, icon_name, left_layout)
        # Agregar separador visual después de los botones
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #555555;")
        left_layout.addWidget(separator)
        # Agregar widget de información de usuario
        user_info_label = QLabel(f"Sesion: {self.username} | Rol: {self.user_role}")
        user_info_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                padding: 5px;
                background-color: #363636;
                border-radius: 3px;
                margin-top: 10px;
            }
        """)
        logout_button = QPushButton("Cerrar Sesión")
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        logout_button.clicked.connect(self.logout)
        
        left_layout.addWidget(user_info_label)
        left_layout.addWidget(logout_button)
        left_layout.addStretch()

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        main_layout.addWidget(right_widget)

        # Agregar la sección de búsqueda mejorada
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        
        # Combo para seleccionar columna
        self.search_combo = QComboBox()
        self.search_combo.addItems([
            "Todos los campos",
            "ID",
            "Fecha",
            "Establecimiento",
            "Tipo Doc.",
            "Nro. Doc.",
            "Materia",
            "Destino",
            "Firma",
            "Estado"
        ])
        search_layout.addWidget(self.search_combo)
        
        # Campo de búsqueda
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar...")
        search_layout.addWidget(self.search_bar)
        
        # Botón de búsqueda
        self.search_button = QPushButton("Buscar")
        self.search_button.clicked.connect(self.apply_filter)
        search_layout.addWidget(self.search_button)
        
        # Botón para limpiar
        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear_filter)
        search_layout.addWidget(self.clear_button)
        
        right_layout.addWidget(search_widget)

        # Agregar el QTreeWidget al lado derecho
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels([
            "ID", "Fecha", "Establecimiento", "Tipo Doc.", 
            "Nro. Doc.", "Materia", "Destino", "Firma", "Estado"
        ])
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
        msg_box.setWindowIcon(QIcon(resource_path("isla_de_maipo.png")))
        msg_box.exec()

    def agregar_datos(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Agregar Documento")
        layout = QFormLayout(dialog)
        # Crear el calendario para la fecha
        fecha_input = QCalendarWidget()
        fecha_input.setGridVisible(True)
        fecha_input.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        
        # Establecer la fecha actual como predeterminada
        fecha_input.setSelectedDate(QDate.currentDate())
        
        # Hacer el calendario más compacto
        fecha_input.setFixedSize(300, 200)
        
        # Estilo oscuro para el calendario
        fecha_input.setStyleSheet("""
            QCalendarWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QCalendarWidget QTableView {
                background-color: #363636;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
                alternate-background-color: #404040;
            }
            QCalendarWidget QTableView:enabled {
                color: #ffffff;
            }
            QCalendarWidget QTableView:disabled {
                color: #808080;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #2b2b2b;
            }
            QCalendarWidget QToolButton {
                color: #ffffff;
                background-color: #363636;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px;
                margin: 3px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #4a4a4a;
            }
            QCalendarWidget QSpinBox {
                color: #ffffff;
                background-color: #363636;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
            }
            QCalendarWidget QMenu {
                color: #ffffff;
                background-color: #363636;
            }
            QCalendarWidget QMenu::item:selected {
                background-color: #4a4a4a;
            }
            /* Estilo para los días de la semana */
            QCalendarWidget QWidget { 
                alternate-background-color: #404040;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #ffffff;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #808080;
            }
        """)

        # Crear inputs para los demás campos
        inputs = {
            'establecimiento': QLineEdit(),
            'tipodocumento': QLineEdit(),
            'nrodocumento': QLineEdit(),
            'materia': QLineEdit(),
            'destino': QLineEdit(),
            'firma': QLineEdit(),
            'estado': QLineEdit()
        }

        # Agregar el calendario primero
        layout.addRow("Fecha:", fecha_input)

        # Agregar los demás campos al formulario
        for label, input_field in inputs.items():
            layout.addRow(label.capitalize() + ":", input_field)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Obtener la fecha seleccionada en formato yyyy-mm-dd
                fecha_seleccionada = fecha_input.selectedDate().toString("yyyy-MM-dd")
                
                DatabaseManager.execute_query(
                    """INSERT INTO documento(
                        fecha, establecimiento, tipodocumento, 
                        nrodocumento, materia, destino, firma, estado
                    ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (fecha_seleccionada,
                     inputs['establecimiento'].text(),
                     inputs['tipodocumento'].text(),
                     inputs['nrodocumento'].text(),
                     inputs['materia'].text(),
                     inputs['destino'].text(),
                     inputs['firma'].text(),
                     inputs['estado'].text())
                )
                
                # Obtener el ID del registro recién insertado
                result = DatabaseManager.execute_query(
                    "SELECT id_documento FROM documento ORDER BY id_documento DESC LIMIT 1"
                )
                last_id = result[0]['id_documento'] if result else 0
                
                self.mostrar_mensaje("Éxito", f"Documento agregado exitosamente con ID: {last_id}")
                self.consultar_datos()
            except Exception as e:
                self.mostrar_mensaje("Error", f"No se pudo agregar el documento: {str(e)}", QMessageBox.Icon.Critical)

    def guardar_datos_seguro(self):
        try:
            data = {key: entry.text() for key, entry in self.entries.items()}
            if not all(data.values()):
                raise ValueError("Todos los campos deben estar llenos")
            
            DatabaseManager.execute_query(
                """INSERT INTO documento(
                    fecha, establecimiento, tipodocumento, 
                    nrodocumento, materia, destino, firma, estado
                ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)""",
                (data['fecha'],
                 data['establecimiento'],
                 data['tipodocumento'],
                 data['nrodocumento'],
                 data['materia'],
                 data['destino'],
                 data['firma'],
                 data['estado'])
            )
            
            for entry in self.entries.values():
                entry.clear()
            
            self.mostrar_mensaje("Éxito", "Datos agregados exitosamente")
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
            total_registros = DatabaseManager.execute_query("SELECT COUNT(*) as total FROM documento")[0]['total']
            resultados = DatabaseManager.execute_query("SELECT * FROM documento")
            
            self.tree_widget.clear()
            
            for i, registro in enumerate(resultados):
                item = QTreeWidgetItem(self.tree_widget)
                item.setText(0, str(registro['id_documento']))
                item.setText(1, str(registro['fecha']))
                item.setText(2, registro['establecimiento'])
                item.setText(3, registro['tipodocumento'])
                item.setText(4, registro['nrodocumento'])
                item.setText(5, registro['materia'])
                item.setText(6, registro['destino'])
                item.setText(7, registro['firma'])
                item.setText(8, registro['estado'])
                
                progress = int(((i + 1) / total_registros) * 100)
                progress_callback.emit(progress)
                time.sleep(0.01)
            
            progress_callback.emit(100)
            return True, f"Se consultaron {total_registros} registros exitosamente"
        except Exception as e:
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
                DatabaseManager.execute_query("DELETE FROM documento WHERE id_documento = %s", (id_to_delete,))
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

        dialog = QDialog(self)
        dialog.setWindowTitle("Modificar Documento")
        layout = QFormLayout(dialog)

        # Crear el calendario para la fecha
        fecha_input = QCalendarWidget()
        fecha_input.setGridVisible(True)
        fecha_input.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        
        # Establecer la fecha actual del registro
        current_date = QDate.fromString(item.text(1), "yyyy-MM-dd")
        fecha_input.setSelectedDate(current_date)
        
        # Hacer el calendario más compacto
        fecha_input.setFixedSize(300, 200)
        
        # Estilo oscuro para el calendario
        fecha_input.setStyleSheet("""
            QCalendarWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QCalendarWidget QTableView {
                background-color: #363636;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
                alternate-background-color: #404040;
            }
            QCalendarWidget QTableView:enabled {
                color: #ffffff;
            }
            QCalendarWidget QTableView:disabled {
                color: #808080;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #2b2b2b;
            }
            QCalendarWidget QToolButton {
                color: #ffffff;
                background-color: #363636;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px;
                margin: 3px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #4a4a4a;
            }
            QCalendarWidget QSpinBox {
                color: #ffffff;
                background-color: #363636;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
            }
            QCalendarWidget QMenu {
                color: #ffffff;
                background-color: #363636;
            }
            QCalendarWidget QMenu::item:selected {
                background-color: #4a4a4a;
            }
            /* Estilo para los días de la semana */
            QCalendarWidget QWidget { 
                alternate-background-color: #404040;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #ffffff;
                selection-background-color: #4a4a4a;
                selection-color: #ffffff;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #808080;
            }
        """)

        # Crear inputs con los valores actuales
        inputs = {
            'establecimiento': QLineEdit(item.text(2)),
            'tipodocumento': QLineEdit(item.text(3)),
            'nrodocumento': QLineEdit(item.text(4)),
            'materia': QLineEdit(item.text(5)),
            'destino': QLineEdit(item.text(6)),
            'firma': QLineEdit(item.text(7)),
            'estado': QLineEdit(item.text(8))
        }

        # Agregar el calendario primero
        layout.addRow("Fecha:", fecha_input)

        # Agregar los demás campos al formulario
        for label, input_field in inputs.items():
            layout.addRow(label.capitalize() + ":", input_field)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Obtener la fecha seleccionada en formato yyyy-mm-dd
                fecha_seleccionada = fecha_input.selectedDate().toString("yyyy-MM-dd")
                
                DatabaseManager.execute_query(
                    """UPDATE documento SET 
                        fecha = %s, establecimiento = %s, tipodocumento = %s,
                        nrodocumento = %s, materia = %s, destino = %s,
                        firma = %s, estado = %s 
                    WHERE id_documento = %s""",
                    (fecha_seleccionada, inputs['establecimiento'].text(),
                     inputs['tipodocumento'].text(), inputs['nrodocumento'].text(),
                     inputs['materia'].text(), inputs['destino'].text(),
                     inputs['firma'].text(), inputs['estado'].text(), id_to_modify)
                )
                self.mostrar_mensaje("Éxito", f"Documento con ID {id_to_modify} modificado exitosamente")
                self.consultar_datos()
            except Exception as e:
                self.mostrar_mensaje("Error", f"No se pudo modificar el documento: {str(e)}", QMessageBox.Icon.Critical)

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
            resultados = DatabaseManager.execute_query("SELECT * FROM documento")
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

    def show_admin_panel(self):
        dialog = AdminPanel(self)
        dialog.exec()

    def logout(self):
        """Función para manejar el cierre de sesión"""
        self.hide()
        
        login = LoginDialog()
        if login.exec() == QDialog.DialogCode.Accepted:
            self.username = login.username_input.text()
            self.user_role = login.get_user_role()
            
            # Actualizar solo la información del usuario
            self.setup_user_info()
            
            # Actualizar visibilidad de botones según el nuevo rol
            for button in self.findChildren(QToolButton):
                if self.user_role == "admin":
                    # El administrador ve todos los botones
                    button.setVisible(True)
                elif self.user_role == "recepcionista":
                    # El recepcionista solo ve agregar y consultar datos
                    if button.objectName() in ["Eliminar Datos", "Modificar Datos", "Administrar"]:
                        button.setVisible(False)
                    else:
                        button.setVisible(True)
                else:  # usuario normal
                    # Usuario normal solo ve consultar
                    if button.objectName() not in ["Consultar Datos"]:
                        button.setVisible(False)
            
            self.show()
        else:
            QApplication.instance().quit()

    def apply_filter(self):
        """Aplica el filtro de búsqueda y agrupa los resultados"""
        text = self.search_bar.text().lower()
        search_column = self.search_combo.currentIndex() - 1
        
        self.tree_widget.clear()
        
        try:
            # Modificar la consulta SQL para ordenar siempre por fecha
            if search_column == -1:  # Todos los campos
                query = """
                    SELECT * FROM documento 
                    WHERE LOWER(fecha) LIKE %s 
                    OR LOWER(establecimiento) LIKE %s 
                    OR LOWER(tipodocumento) LIKE %s 
                    OR LOWER(nrodocumento) LIKE %s 
                    OR LOWER(materia) LIKE %s 
                    OR LOWER(destino) LIKE %s 
                    OR LOWER(firma) LIKE %s 
                    OR LOWER(estado) LIKE %s
                    ORDER BY fecha DESC
                """
                search_pattern = f"%{text}%"
                params = (search_pattern,) * 8
            elif search_column == 1:  # Fecha
                query = """
                    SELECT *, YEAR(fecha) as año 
                    FROM documento 
                    WHERE LOWER(fecha) LIKE %s
                    ORDER BY fecha DESC
                """
                params = (f"%{text}%",)
            else:
                campos = ['id_documento', 'fecha', 'establecimiento', 'tipodocumento', 
                         'nrodocumento', 'materia', 'destino', 'firma', 'estado']
                campo = campos[search_column]
                query = f"""
                    SELECT * FROM documento 
                    WHERE LOWER({campo}) LIKE %s
                    ORDER BY fecha DESC
                """
                params = (f"%{text}%",)
            
            resultados = DatabaseManager.execute_query(query, params)
            
            # Agrupar resultados
            resultados_agrupados = {}
            for registro in resultados:
                if search_column == -1:  # Todos los campos
                    for campo in ['fecha', 'establecimiento', 'tipodocumento', 
                                'nrodocumento', 'materia', 'destino', 'firma', 'estado']:
                        if text in str(registro[campo]).lower():
                            grupo = f"{campo.upper()}: {str(registro[campo]).upper()}"
                            break
                    else:
                        grupo = "OTROS"
                elif search_column == 1:  # Fecha
                    año = registro['año'] if 'año' in registro else registro['fecha'].year
                    grupo = f"AÑO {año}"
                else:
                    grupo = str(registro[campos[search_column]]).upper()
                
                if grupo not in resultados_agrupados:
                    resultados_agrupados[grupo] = []
                resultados_agrupados[grupo].append(registro)
            
            # Ordenar los grupos
            grupos_ordenados = sorted(resultados_agrupados.items())
            if search_column == 1:
                grupos_ordenados = sorted(resultados_agrupados.items(), reverse=True)
            
            # Crear los grupos en el tree widget
            for grupo, registros in grupos_ordenados:
                grupo_item = QTreeWidgetItem(self.tree_widget)
                grupo_item.setText(0, grupo)
                grupo_item.setExpanded(True)
                
                # Establecer color de fondo para el grupo
                for columna in range(self.tree_widget.columnCount()):
                    grupo_item.setBackground(columna, QColor("#2c2c2c"))
                
                # Estilo para los grupos
                font = grupo_item.font(0)
                font.setBold(True)
                grupo_item.setFont(0, font)
                
                # Agregar registros
                for registro in registros:
                    item = QTreeWidgetItem(grupo_item)
                    item.setText(0, str(registro['id_documento']))
                    item.setText(1, str(registro['fecha']))
                    item.setText(2, registro['establecimiento'])
                    item.setText(3, registro['tipodocumento'])
                    item.setText(4, registro['nrodocumento'])
                    item.setText(5, registro['materia'])
                    item.setText(6, registro['destino'])
                    item.setText(7, registro['firma'])
                    item.setText(8, registro['estado'])
                    
                    # Color de fondo para los items
                    for columna in range(self.tree_widget.columnCount()):
                        item.setBackground(columna, QColor("#1a1a1a"))
            
        except Exception as e:
            self.mostrar_mensaje("ERROR", f"ERROR AL REALIZAR LA BÚSQUEDA: {str(e)}", 
                               QMessageBox.Icon.Critical)

    def clear_filter(self):
        """Limpia el filtro y muestra todos los registros sin agrupar"""
        self.search_bar.clear()
        self.search_combo.setCurrentIndex(0)
        self.consultar_datos()

class RegisterDialog(QDialog):
    def __init__(self, parent=None, admin_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Registro de Usuario")
        self.setFixedWidth(300)
        
        layout = QFormLayout(self)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Combo box para selección de rol (solo visible para administradores)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["usuario", "recepcionista", "admin"])
        
        layout.addRow("Usuario:", self.username_input)
        layout.addRow("Contraseña:", self.password_input)
        layout.addRow("Confirmar Contraseña:", self.confirm_password_input)
        
        # Solo mostrar selección de rol si es modo admin
        if admin_mode:
            layout.addRow("Rol:", self.role_combo)
        else:
            self.role_combo.setCurrentText("usuario")
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.register)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def register(self):
        try:
            username = self.username_input.text()
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()
            role = self.role_combo.currentText()
            
            if not all([username, password, confirm_password]):
                raise ValueError("Todos los campos son obligatorios")
            
            if password != confirm_password:
                raise ValueError("Las contraseñas no coinciden")
            
            if len(password) < 8:
                raise ValueError("La contraseña debe tener al menos 8 caracteres")
                
            DatabaseManager.register_user(username, password, role)
            QMessageBox.information(self, "xito", "Usuario registrado correctamente")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inicio de Sesión")
        self.setFixedWidth(300)
        self.user_role = None
        
        layout = QFormLayout(self)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        layout.addRow("Usuario:", self.username_input)
        layout.addRow("Contraseña:", self.password_input)
        
        buttons = QHBoxLayout()
        
        login_btn = QPushButton("Iniciar Sesión")
        register_btn = QPushButton("Registrarse")
        
        login_btn.clicked.connect(self.login)
        register_btn.clicked.connect(self.show_register)
        
        buttons.addWidget(login_btn)
        buttons.addWidget(register_btn)
        
        layout.addRow(buttons)

    def login(self):
        try:
            username = self.username_input.text()
            password = self.password_input.text()
            
            if not all([username, password]):
                raise ValueError("Todos los campos son obligatorios")
                
            success, role = DatabaseManager.validate_login(username, password)
            if success:
                self.user_role = role
                self.accept()
            else:
                raise ValueError("Usuario o contraseña incorrectos")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def show_register(self):
        dialog = RegisterDialog(self)
        dialog.exec()

    def get_user_role(self):
        return self.user_role

class AdminPanel(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Panel de Administración")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Tabla de usuarios
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(3)
        self.user_table.setHorizontalHeaderLabels(["Usuario", "Rol Actual", "Nuevo Rol"])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.user_table)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Guardar Cambios")
        save_button.clicked.connect(self.save_changes)
        
        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.load_users)
        
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)
        
        self.load_users()

    def load_users(self):
        try:
            users = DatabaseManager.execute_query("""
                SELECT nombreusuario, rol 
                FROM usuario 
                ORDER BY nombreusuario
            """)
            
            self.user_table.setRowCount(len(users))
            
            for i, user in enumerate(users):
                # Usuario
                self.user_table.setItem(i, 0, QTableWidgetItem(user['nombreusuario']))
                
                # Rol actual
                self.user_table.setItem(i, 1, QTableWidgetItem(user['rol']))
                
                # Combo box para nuevo rol
                role_combo = QComboBox()
                role_combo.addItems(["usuario", "recepcionista", "admin"])
                role_combo.setCurrentText(user['rol'])
                self.user_table.setCellWidget(i, 2, role_combo)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar usuarios: {str(e)}")

    def save_changes(self):
        try:
            changes_made = False
            for row in range(self.user_table.rowCount()):
                username = self.user_table.item(row, 0).text()
                current_role = self.user_table.item(row, 1).text()
                new_role = self.user_table.cellWidget(row, 2).currentText()
                
                if current_role != new_role:
                    DatabaseManager.execute_query("""
                        UPDATE usuario 
                        SET rol = %s 
                        WHERE nombreusuario = %s
                    """, (new_role, username))
                    changes_made = True
            
            if changes_made:
                QMessageBox.information(self, "Éxito", "Roles actualizados correctamente")
                self.load_users()
            else:
                QMessageBox.information(self, "Info", "No se realizaron cambios")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar cambios: {str(e)}")
def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("isla_de_maipo.png")))
    
    # Mostramos el diálogo de login
    login = LoginDialog()
    if login.exec() == QDialog.DialogCode.Accepted:
        user_role = login.get_user_role()
        username = login.username_input.text()  # Obtener el nombre de usuario
        window = MainWindow(username=username, user_role=user_role)  # Pasar los datos
        
        # Configurar visibilidad de botones según el rol del usuario
        for button in window.findChildren(QToolButton):
            if user_role == "admin":
                # El administrador ve todos los botones
                button.setVisible(True)
            elif user_role == "recepcionista":
                # El recepcionista solo ve agregar y consultar datos
                if button.objectName() in ["Eliminar Datos", "Modificar Datos", "Administrar"]:
                    button.setVisible(False)
                else:
                    button.setVisible(True)
            else:  # usuario normal
                # Usuario normal solo ve consultar
                if button.objectName() not in ["Consultar Datos"]:
                    button.setVisible(False)  
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit()
if __name__ == "__main__":
    main()
