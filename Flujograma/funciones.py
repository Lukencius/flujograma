from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QToolButton, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QMessageBox,
                             QPushButton, QInputDialog, QDialog, QDialogButtonBox, QProgressBar, QFormLayout,
                             QTableWidget, QTableWidgetItem, QComboBox, QFrame, QCalendarWidget, QProgressDialog,
                             QHeaderView)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QDate
from PyQt6.QtGui import QIcon, QColor, QPixmap, QFont
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

# Constantes de colores (agregar al inicio del archivo)
COLORS = {
    'primary': '#1E88E5',      # Azul principal
    'primary_dark': '#1565C0', # Azul oscuro para hover
    'primary_light': '#64B5F6', # Azul claro
    'background': '#1a1f2c',   # Fondo oscuro azulado
    'surface': '#2a3142',      # Superficie de componentes
    'error': '#EF5350',        # Rojo para errores
    'success': '#4CAF50',      # Verde para éxito
    'text': '#ffffff',         # Texto blanco
    'text_secondary': '#8F9BBA' # Texto secundario más claro y visible para los placeholders
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
                time.sleep(0.001)
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

    def init_ui(self):
        self.setWindowTitle("Interfaz de Corporación Isla de Maipo")
        self.setGeometry(100, 100, 1200, 700)
        self.setWindowIcon(QIcon(resource_path("isla_de_maipo.png")))
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Panel izquierdo
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(10, 20, 10, 20)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        scaled_pixmap = logo_pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio)
        logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(logo_label)

        # Contenedor para el título y la línea
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(5)
        title_layout.setContentsMargins(0, 0, 0, 15)  # Añadido margen inferior

        # Título sin fondo
        title_label = QLabel("Corporación de Isla de Maipo")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                letter-spacing: 0.5px;
                padding: 5px 0px;
            }
        """)
        title_layout.addWidget(title_label)

        # Línea separadora sutil
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("""
            QFrame {
                border: none;
                background-color: rgba(30, 136, 229, 0.5);
                max-height: 1px;
                margin: 0px 40px;
            }
        """)
        title_layout.addWidget(line)
        
        left_layout.addWidget(title_container)

        # Botones
        buttons_data = [
            ("Agregar Datos", self.agregar_datos),
            ("Consultar Datos", self.consultar_datos),
            ("Eliminar Datos", self.eliminar_datos),
            ("Modificar Datos", self.modificar_datos),
            ("Administrar", self.show_admin_panel)
        ]

        for text, slot in buttons_data:
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface']};
                    color: white;
                    border: none;
                    padding: 15px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary']};
                }}
                QPushButton:pressed {{
                    background-color: {COLORS['primary_dark']};
                }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            left_layout.addWidget(btn)

        # Información de usuario y botón de cerrar sesión
        left_layout.addStretch()
        
        # Panel de información de usuario
        user_info = QLabel(f"Usuario: {self.username}\nRol: {self.user_role}")
        user_info.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: {COLORS['surface']};
                padding: 10px;
                border-radius: 8px;
                font-size: 13px;
            }}
        """)
        left_layout.addWidget(user_info)

        # Botón de cerrar sesión
        logout_btn = QPushButton("Cerrar Sesión")
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['error']};
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
        """)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self.logout)
        left_layout.addWidget(logout_btn)

        main_layout.addWidget(left_panel, 1)

        # Panel derecho (resto del código del panel derecho permanece igual)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(10)

        # Contenedor para la barra de búsqueda y botones
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)

        # Combo de búsqueda
        self.search_combo = QComboBox()
        self.search_combo.addItems([
            "Todos los campos",
            "Agrupar por Año",    # Nueva opción
            "Agrupar por Estado", # Nueva opción
            "Fecha",
            "Establecimiento",
            "Tipo Documento",
            "Nro Documento",
            "Materia",
            "Destino",
            "Firma",
            "Estado"
        ])
        self.search_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                padding: 8px;
                border: 2px solid {COLORS['primary']};
                border-radius: 6px;
                min-width: 150px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary_light']};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox::down-arrow {{
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }}
        """)

        # Barra de búsqueda
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar...")
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                padding: 8px 12px;
                border: 2px solid {COLORS['primary']};
                border-radius: 6px;
                font-size: 14px;
                min-width: 300px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary_light']};
            }}
            QLineEdit::placeholder {{
                color: {COLORS['text_secondary']};
            }}
        """)

        # Botón de búsqueda
        search_btn = QPushButton("Buscar")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 8px 15px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
                transform: translateY(-2px);
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
                transform: translateY(1px);
            }}
        """)
        search_btn.clicked.connect(self.perform_search)

        # Botón de limpiar
        clear_btn = QPushButton("Limpiar")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 2px solid {COLORS['primary']};
                padding: 8px 15px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                border-color: {COLORS['primary']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary_dark']};
            }}
        """)
        clear_btn.clicked.connect(self.clear_search)

        # Agregar widgets al layout de búsqueda
        search_layout.addWidget(self.search_combo)
        search_layout.addWidget(self.search_bar, 1)  # El 1 le da prioridad en el espacio
        search_layout.addWidget(search_btn)
        search_layout.addWidget(clear_btn)

        # Agregar el contenedor de búsqueda al layout principal
        right_layout.addWidget(search_container)

        # TreeWidget para mostrar datos
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels([
            "ID", "Fecha", "Establecimiento", "Tipo Doc", 
            "Nro Doc", "Materia", "Destino", "Firma", "Estado"
        ])
        self.tree_widget.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: none;
                border-radius: 6px;
            }}
            QTreeWidget::item {{
                padding: 5px;
            }}
            QTreeWidget::item:selected {{
                background-color: {COLORS['primary']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                padding: 5px;
                border: none;
            }}
        """)
        right_layout.addWidget(self.tree_widget)

        # Agregar el panel derecho al layout principal
        main_layout.addWidget(right_panel, 4)

        # Estilo general de la ventana
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QWidget {{
                color: white;
            }}
        """)

        # Conectar la señal del botón de búsqueda
        search_btn.clicked.connect(self.perform_search)
        # También permitir búsqueda al presionar Enter en la barra de búsqueda
        self.search_bar.returnPressed.connect(self.perform_search)

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
        try:
            # Configurar las columnas del TreeWidget
            self.tree_widget.setColumnCount(9)
            self.tree_widget.setHeaderLabels([
                "ID", "Fecha", "Establecimiento", "Tipo Doc",
                "Nro Doc", "Materia", "Destino", "Firma", "Estado"
            ])

            # Obtener los datos
            resultados = DatabaseManager.execute_query(
                "SELECT * FROM documento ORDER BY id_documento"
            )

            # Limpiar el TreeWidget
            self.tree_widget.clear()

            # Agregar los datos al TreeWidget
            for registro in resultados:
                item = QTreeWidgetItem(self.tree_widget)
                item.setText(0, str(registro['id_documento']))
                item.setText(1, str(registro['fecha']))
                item.setText(2, str(registro['establecimiento']))
                item.setText(3, str(registro['tipodocumento']))
                item.setText(4, str(registro['nrodocumento']))
                item.setText(5, str(registro['materia']))
                item.setText(6, str(registro['destino']))
                item.setText(7, str(registro['firma']))
                item.setText(8, str(registro['estado']))

            # Ajustar el ancho de las columnas
            for i in range(9):
                self.tree_widget.resizeColumnToContents(i)

            # Mostrar mensaje de éxito
            QMessageBox.information(
                self,
                "Consulta exitosa",
                f"Se cargaron {len(resultados)} registros"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al consultar datos: {str(e)}"
            )

    def mostrar_mensaje(self, titulo, mensaje, icono=QMessageBox.Icon.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(titulo)
        msg.setText(mensaje)
        msg.setIcon(icono)
        msg.exec()

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
                DatabaseManager.execute_query("DELETE FROM documento WHERE id = %s", (id_to_delete,))
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

    def perform_search(self):
        """Realizar la búsqueda con agrupación automática"""
        search_text = self.search_bar.text().strip().lower()
        search_field = self.search_combo.currentText()

        try:
            # Obtener todos los registros
            resultados = DatabaseManager.execute_query(
                "SELECT * FROM documento ORDER BY fecha DESC"
            )

            # Limpiar el TreeWidget
            self.tree_widget.clear()

            # Mapeo de campos a índices
            column_indices = {
                "Todos los campos": -1,
                "Fecha": 1,
                "Establecimiento": 2,
                "Tipo Documento": 3,
                "Nro Documento": 4,
                "Materia": 5,
                "Destino": 6,
                "Firma": 7,
                "Estado": 8
            }

            # Filtrar resultados
            search_column = column_indices.get(search_field, -1)
            resultados_filtrados = []

            for registro in resultados:
                if search_text:  # Solo filtrar si hay texto de búsqueda
                    if search_column == -1:  # Todos los campos
                        valores = [str(v) for v in registro.values()]
                        if any(search_text in str(valor).lower() for valor in valores):
                            resultados_filtrados.append(registro)
                    else:
                        campo = list(registro.values())[search_column]
                        if search_text in str(campo).lower():
                            resultados_filtrados.append(registro)
                else:
                    resultados_filtrados = resultados

            # Agrupar resultados por año y estado
            grupos_año = {}
            for registro in resultados_filtrados:
                # Extraer el año de la fecha
                fecha = str(registro['fecha'])
                año = fecha.split('-')[0] if '-' in fecha else 'Sin Año'
                
                if año not in grupos_año:
                    grupos_año[año] = {'registros': [], 'estados': {}}
                grupos_año[año]['registros'].append(registro)
                
                # Subgrupo por estado
                estado = registro['estado'] or 'Sin Estado'
                if estado not in grupos_año[año]['estados']:
                    grupos_año[año]['estados'][estado] = []
                grupos_año[año]['estados'][estado].append(registro)

            # Mostrar resultados agrupados
            total_registros = 0
            años_ordenados = sorted(grupos_año.keys(), reverse=True)

            for año in años_ordenados:
                registros_año = grupos_año[año]['registros']
                # Crear grupo de año
                año_item = QTreeWidgetItem(self.tree_widget)
                año_item.setText(0, f"▼ Año {año} ({len(registros_año)} documentos)")
                año_item.setExpanded(True)

                # Estilo para el grupo de año
                for col in range(9):
                    año_item.setBackground(col, QColor(COLORS['primary_dark']))
                    font = año_item.font(col)
                    font.setBold(True)
                    año_item.setFont(col, font)

                # Subgrupos por estado
                estados = grupos_año[año]['estados']
                for estado, registros_estado in estados.items():
                    # Crear subgrupo de estado
                    estado_item = QTreeWidgetItem(año_item)
                    estado_item.setText(0, f"▼ Estado: {estado} ({len(registros_estado)} documentos)")
                    estado_item.setExpanded(True)

                    # Estilo para el subgrupo de estado
                    for col in range(9):
                        estado_item.setBackground(col, QColor(COLORS['surface']))
                        font = estado_item.font(col)
                        font.setBold(True)
                        estado_item.setFont(col, font)

                    # Agregar registros al subgrupo
                    for registro in registros_estado:
                        item = QTreeWidgetItem(estado_item)
                        item.setText(0, str(registro['id_documento']))
                        item.setText(1, str(registro['fecha']))
                        item.setText(2, str(registro['establecimiento']))
                        item.setText(3, str(registro['tipodocumento']))
                        item.setText(4, str(registro['nrodocumento']))
                        item.setText(5, str(registro['materia']))
                        item.setText(6, str(registro['destino']))
                        item.setText(7, str(registro['firma']))
                        item.setText(8, str(registro['estado']))
                        total_registros += 1

            # Ajustar columnas
            for i in range(9):
                self.tree_widget.resizeColumnToContents(i)

            # Mostrar mensaje con resultados
            if search_text:
                QMessageBox.information(
                    self,
                    "Resultados de búsqueda",
                    f"Se encontraron {total_registros} registros que coinciden con '{search_text}'\n"
                    f"Agrupados en {len(grupos_año)} años diferentes"
                )
            else:
                QMessageBox.information(
                    self,
                    "Registros agrupados",
                    f"Se muestran {total_registros} registros\n"
                    f"Agrupados en {len(grupos_año)} años diferentes"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al realizar la búsqueda: {str(e)}"
            )

    def clear_search(self):
        """Limpiar la búsqueda y mostrar todos los registros sin agrupar"""
        self.search_bar.clear()
        self.search_combo.setCurrentIndex(0)
        
        try:
            # Recargar todos los datos sin agrupar
            resultados = DatabaseManager.execute_query(
                "SELECT * FROM documento ORDER BY id_documento"
            )
            
            self.tree_widget.clear()
            for registro in resultados:
                item = QTreeWidgetItem(self.tree_widget)
                item.setText(0, str(registro['id_documento']))
                item.setText(1, str(registro['fecha']))
                item.setText(2, str(registro['establecimiento']))
                item.setText(3, str(registro['tipodocumento']))
                item.setText(4, str(registro['nrodocumento']))
                item.setText(5, str(registro['materia']))
                item.setText(6, str(registro['destino']))
                item.setText(7, str(registro['firma']))
                item.setText(8, str(registro['estado']))

            # Ajustar columnas
            for i in range(9):
                self.tree_widget.resizeColumnToContents(i)

            QMessageBox.information(
                self,
                "Búsqueda limpiada",
                f"Se están mostrando todos los registros ({len(resultados)})"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al limpiar la búsqueda: {str(e)}"
            )

    # Método auxiliar para depuración
    def print_tree_content(self):
        """Imprimir el contenido del TreeWidget para depuración"""
        print("\nContenido del TreeWidget:")
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            row_content = []
            for j in range(item.columnCount()):
                row_content.append(item.text(j))
            print(f"Fila {i}: {row_content}")

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

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inicio de Sesión - Corporación Isla de Maipo")
        self.setFixedWidth(450)
        self.setFixedHeight(500)
        self.user_role = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        scaled_pixmap = logo_pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(logo_label)

        # Título
        title_label = QLabel("Bienvenido")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 20px;
            }
        """)
        main_layout.addWidget(title_label)

        # Formulario
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(15)

        # Usuario
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Ingrese su usuario")
        self.username_input.setStyleSheet(create_input_style())
        self.username_input.setMinimumHeight(42)
        self.username_input.setFont(QFont("Segoe UI", 14))

        # Contraseña
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Ingrese su contraseña")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(create_input_style())
        self.password_input.setMinimumHeight(42)
        self.password_input.setFont(QFont("Segoe UI", 14))

        form_layout.addRow(self.create_label("Usuario:"), self.username_input)
        form_layout.addRow(self.create_label("Contraseña:"), self.password_input)

        main_layout.addWidget(form_widget)

        # Botones
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(10)

        # Botón de inicio de sesión
        login_btn = QPushButton("Iniciar Sesión")
        login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
            }}
        """)
        login_btn.clicked.connect(self.login)
        buttons_layout.addWidget(login_btn)

        # Botón de registro
        register_btn = QPushButton("Registrarse")
        register_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['primary']};
                border: 2px solid {COLORS['primary']};
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(33, 150, 243, 0.1);
            }}
            QPushButton:pressed {{
                background-color: rgba(33, 150, 243, 0.2);
            }}
        """)
        register_btn.clicked.connect(self.show_register)
        buttons_layout.addWidget(register_btn)

        main_layout.addLayout(buttons_layout)

        # Estilo general del diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
        """)

    def create_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        return label

    def login(self):
        try:
            username = self.username_input.text()
            password = self.password_input.text()
            
            if not username or not password:
                self.show_custom_error("Campos Incompletos", 
                    "Por favor complete todos los campos para iniciar sesión.",
                    "Los campos de usuario y contraseña son obligatorios.")
                return
                
            success, role = DatabaseManager.validate_login(username, password)
            if success:
                self.user_role = role
                self.accept()
            else:
                self.show_custom_error("Error de Autenticación", 
                    "No se pudo iniciar sesión con las credenciales proporcionadas.",
                    "Por favor verifique su usuario y contraseña.")
        except Exception as e:
            self.show_error_message(str(e))

    def show_custom_error(self, title, message, detail):
        error_dialog = QDialog(self)
        error_dialog.setWindowTitle(title)
        error_dialog.setFixedWidth(400)
        
        layout = QVBoxLayout(error_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Icono de error
        icon_label = QLabel()
        icon_label.setText("⚠️")
        icon_label.setStyleSheet("""
            QLabel {
                color: #EF5350;
                font-size: 48px;
            }
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Mensaje principal
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        # Detalle
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 14px;
            }}
        """)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail_label)

        # Botón de cerrar
        close_btn = QPushButton("Entendido")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
            }}
        """)
        close_btn.clicked.connect(error_dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Estilo general del diálogo
        error_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
        """)

        error_dialog.exec()

    def show_register(self):
        dialog = RegisterDialog(self)
        dialog.exec()

    def get_user_role(self):
        return self.user_role

class RegisterDialog(QDialog):
    def __init__(self, parent=None, admin_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Registro de Usuario - Corporación Isla de Maipo")
        self.setFixedWidth(450)
        self.setFixedHeight(550)
        self.admin_mode = admin_mode
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        scaled_pixmap = logo_pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(logo_label)

        # Título
        title_label = QLabel("Registro de Usuario")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 20px;
            }
        """)
        main_layout.addWidget(title_label)

        # Formulario
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(15)

        # Campos de entrada
        self.username_input = self.create_input("Ingrese un nombre de usuario")
        self.password_input = self.create_input("Ingrese una contraseña segura", is_password=True)
        self.confirm_password_input = self.create_input("Confirme su contraseña", is_password=True)
        
        form_layout.addRow(self.create_label("Usuario:"), self.username_input)
        form_layout.addRow(self.create_label("Contraseña:"), self.password_input)
        form_layout.addRow(self.create_label("Confirmar:"), self.confirm_password_input)

        # Combo box para rol (solo en modo admin)
        if self.admin_mode:
            self.role_combo = QComboBox()
            self.role_combo.addItems(["usuario", "recepcionista", "admin"])
            self.role_combo.setStyleSheet(f"""
                QComboBox {{
                    padding: 8px;
                    border: 2px solid {COLORS['surface']};
                    border-radius: 6px;
                    background-color: {COLORS['surface']};
                    color: {COLORS['text']};
                    min-width: 150px;
                }}
                QComboBox::drop-down {{
                    border: none;
                    padding-right: 20px;
                }}
                QComboBox::down-arrow {{
                    image: url(down_arrow.png);
                    width: 12px;
                    height: 12px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {COLORS['surface']};
                    color: {COLORS['text']};
                    selection-background-color: {COLORS['primary']};
                    selection-color: {COLORS['text']};
                    border: 1px solid {COLORS['primary']};
                }}
            """)
            form_layout.addRow(self.create_label("Rol:"), self.role_combo)
        else:
            self.role_combo = QComboBox()
            self.role_combo.addItem("usuario")
            self.role_combo.hide()

        main_layout.addWidget(form_widget)

        # Botones
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(10)

        # Botón de registro con animaciones y efectos mejorados
        register_btn = QPushButton("Registrar Usuario")
        register_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 150px;
                transition: all 0.3s;
                position: relative;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
                transform: translateY(1px);
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
            }}
        """)
        register_btn.clicked.connect(self.register)
        buttons_layout.addWidget(register_btn)

        # Botón cancelar con animaciones mejoradas
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['error']};
                border: 2px solid {COLORS['error']};
                padding: 12px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 150px;
                transition: all 0.3s;
            }}
            QPushButton:hover {{
                background-color: {COLORS['error']};
                color: {COLORS['text']};
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(239, 83, 80, 0.2);
            }}
            QPushButton:pressed {{
                transform: translateY(1px);
                box-shadow: none;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        main_layout.addLayout(buttons_layout)

        # Estilo general del diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
        """)

    def create_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        return label

    def create_input(self, placeholder, is_password=False):
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        if is_password:
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
        input_field.setStyleSheet(create_input_style())
        input_field.setMinimumHeight(42)
        input_field.setFont(QFont("Segoe UI", 14))
        return input_field

    def register(self):
        try:
            username = self.username_input.text()
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()
            role = self.role_combo.currentText()
            
            if not all([username, password, confirm_password]):
                self.show_custom_error(
                    "Campos Incompletos",
                    "Por favor complete todos los campos para registrarse.",
                    "Todos los campos son obligatorios para crear una cuenta."
                )
                return
            
            if password != confirm_password:
                self.show_custom_error(
                    "Contraseñas No Coinciden",
                    "Las contraseñas ingresadas no coinciden.",
                    "Por favor asegúrese de que ambas contraseñas sean idénticas."
                )
                return
            
            if len(password) < 8:
                self.show_custom_error(
                    "Contraseña Débil",
                    "La contraseña debe tener al menos 8 caracteres.",
                    "Use una combinación de letras, números y símbolos para mayor seguridad."
                )
                return
            
            if not any(c.isupper() for c in password):
                self.show_custom_error(
                    "Contraseña Inválida",
                    "La contraseña debe contener al menos una mayúscula.",
                    "Incluya al menos una letra mayúscula para fortalecer su contraseña."
                )
                return
            
            if not any(c.isdigit() for c in password):
                self.show_custom_error(
                    "Contraseña Inválida",
                    "La contraseña debe contener al menos un número.",
                    "Incluya al menos un número para fortalecer su contraseña."
                )
                return
                
            DatabaseManager.register_user(username, password, role)
            self.show_custom_success(
                "Registro Exitoso",
                "¡Usuario registrado correctamente!",
                "Ya puede iniciar sesión con sus credenciales."
            )
            self.accept()
        except Exception as e:
            self.show_custom_error(
                "Error de Registro",
                "No se pudo completar el registro.",
                str(e)
            )

    def show_custom_error(self, title, message, detail):
        error_dialog = QDialog(self)
        error_dialog.setWindowTitle(title)
        error_dialog.setFixedWidth(400)
        
        layout = QVBoxLayout(error_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Icono de error
        icon_label = QLabel()
        icon_label.setText("⚠️")
        icon_label.setStyleSheet("""
            QLabel {
                color: #EF5350;
                font-size: 48px;
            }
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Mensaje principal
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        # Detalle
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 14px;
            }}
        """)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail_label)

        # Botón de cerrar
        close_btn = QPushButton("Entendido")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
            }}
        """)
        close_btn.clicked.connect(error_dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Estilo general del diálogo
        error_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
        """)

        error_dialog.exec()

    def show_custom_success(self, title, message, detail):
        success_dialog = QDialog(self)
        success_dialog.setWindowTitle(title)
        success_dialog.setFixedWidth(400)
        
        layout = QVBoxLayout(success_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Icono de éxito
        icon_label = QLabel()
        icon_label.setText("✅")
        icon_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 48px;
            }
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Mensaje principal
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        # Detalle
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 14px;
            }}
        """)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail_label)

        # Botón de cerrar
        close_btn = QPushButton("Continuar")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: {COLORS['text']};
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: #43A047;
            }}
            QPushButton:pressed {{
                background-color: #388E3C;
            }}
        """)
        close_btn.clicked.connect(success_dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Estilo general del diálogo
        success_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
        """)

        success_dialog.exec()

    def validate_username(self):
        text = self.username_input.text()
        validation_result = {
            'valid': True,
            'message': "",
            'details': []
        }

        # Validaciones con mensajes detallados
        if len(text) < 4:
            validation_result['valid'] = False
            validation_result['message'] = "Usuario demasiado corto"
            validation_result['details'] = [
                "Mínimo 4 caracteres requeridos",
                f"Actualmente: {len(text)} caracteres"
            ]
        elif not text.isalnum():
            validation_result['valid'] = False
            validation_result['message'] = "Caracteres no permitidos"
            validation_result['details'] = [
                "Solo se permiten letras y números",
                "No usar espacios ni caracteres especiales"
            ]
        else:
            validation_result['message'] = "Usuario válido"
            validation_result['details'] = [
                "Formato correcto",
                "Longitud adecuada"
            ]

        self.update_field_status(
            self.username_status, 
            self.username_input,
            validation_result
        )
        return validation_result['valid']

    def validate_password(self):
        text = self.password_input.text()
        validation_result = {
            'valid': True,
            'message': "",
            'details': []
        }

        # Lista de verificación de requisitos
        requirements = []
        requirements.append(('length', len(text) >= 8, "Mínimo 8 caracteres"))
        requirements.append(('uppercase', any(c.isupper() for c in text), "Una mayúscula"))
        requirements.append(('digit', any(c.isdigit() for c in text), "Un número"))

        # Verificar requisitos
        failed_requirements = [req[2] for req in requirements if not req[1]]

        if failed_requirements:
            validation_result['valid'] = False
            validation_result['message'] = "Contraseña débil"
            validation_result['details'] = [
                "Requisitos faltantes:",
                *failed_requirements
            ]
        else:
            validation_result['message'] = "Contraseña segura"
            validation_result['details'] = [
                "Cumple todos los requisitos",
                "✓ Longitud adecuada",
                "✓ Incluye mayúsculas",
                "✓ Incluye números"
            ]

        self.update_field_status(
            self.password_status,
            self.password_input,
            validation_result
        )
        return validation_result['valid']

    def update_field_status(self, status_label, input_field, validation):
        # Actualizar el icono y tooltip
        icon = "✓" if validation['valid'] else "⚠️"
        
        # Crear tooltip detallado
        tooltip = f"""
        <h3 style='color: {"#4CAF50" if validation["valid"] else "#EF5350"};'>
            {validation['message']}
        </h3>
        <ul style='margin: 5px 0;'>
            {"".join(f"<li>{detail}</li>" for detail in validation['details'])}
        </ul>
        """
        
        # Actualizar el estilo del campo según validación
        input_field.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px 12px;
                border: 2px solid {COLORS['success'] if validation['valid'] else COLORS['error']};
                border-radius: 6px;
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                font-size: 14px;
                transition: all 0.3s;
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['primary']};
            }}
            QLineEdit::placeholder {{
                color: {COLORS['text_secondary']};
                font-size: 15px;
                opacity: 0.95;
                font-weight: 450;
                letter-spacing: 0.4px;
            }}
        """)

        # Actualizar el label de estado
        status_label.setText(icon)
        status_label.setToolTip(tooltip)
        status_label.setStyleSheet("""
            QLabel {
                margin-left: 5px;
                font-size: 16px;
                padding: 5px;
            }
            QToolTip {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
        """)

class AdminPanel(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Panel de Administración")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title_label = QLabel("Administración de Usuarios")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
                background-color: {COLORS['surface']};
                border-radius: 8px;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Tabla de usuarios
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(3)
        self.user_table.setHorizontalHeaderLabels(["Usuario", "Rol Actual", "Nuevo Rol"])
        self.user_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: none;
                border-radius: 8px;
                gridline-color: {COLORS['primary']};
            }}
            QTableWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {COLORS['primary']};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['primary']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['primary_dark']};
                color: {COLORS['text']};
                padding: 10px;
                border: none;
                font-weight: bold;
            }}
            QScrollBar:vertical {{
                background: {COLORS['surface']};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['primary']};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.user_table)

        # Contenedor de botones
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(10)

        # Botón Actualizar
        refresh_button = QPushButton("Actualizar Lista")
        refresh_button.clicked.connect(self.load_users)
        refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 2px solid {COLORS['primary']};
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                border-color: {COLORS['primary']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary_dark']};
            }}
        """)

        # Botón Guardar
        save_button = QPushButton("Guardar Cambios")
        save_button.clicked.connect(self.save_changes)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
                transform: translateY(-2px);
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
                transform: translateY(1px);
            }}
        """)

        button_layout.addWidget(refresh_button)
        button_layout.addWidget(save_button)
        layout.addWidget(button_container)

        # Estilo del ComboBox para roles
        self.combo_style = f"""
            QComboBox {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                padding: 5px;
                border: 2px solid {COLORS['primary']};
                border-radius: 4px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary_light']};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['primary']};
                selection-color: {COLORS['text']};
            }}
        """

        # Estilo general del diálogo
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
        """)

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
                username_item = QTableWidgetItem(user['nombreusuario'])
                username_item.setForeground(QColor(COLORS['text']))
                self.user_table.setItem(i, 0, username_item)
                
                # Rol actual
                current_role_item = QTableWidgetItem(user['rol'])
                current_role_item.setForeground(QColor(COLORS['text']))
                self.user_table.setItem(i, 1, current_role_item)
                
                # Combo box para nuevo rol
                role_combo = QComboBox()
                role_combo.addItems(["usuario", "recepcionista", "admin"])
                role_combo.setCurrentText(user['rol'])
                role_combo.setStyleSheet(self.combo_style)
                self.user_table.setCellWidget(i, 2, role_combo)

            # Ajustar tamaño de columnas
            self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            
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

# Función auxiliar para crear el estilo de input (para reutilizar en ambas clases)
def create_input_style():
    return f"""
        QLineEdit {{
            padding: 10px 12px;
            border: 2px solid {COLORS['surface']};
            border-radius: 6px;
            background-color: {COLORS['surface']};
            color: {COLORS['text']};
            font-size: 14px;
        }}
        QLineEdit:focus {{
            border: 2px solid {COLORS['primary']};
            background-color: {COLORS['surface']};
        }}
        QLineEdit::placeholder {{
            color: {COLORS['text_secondary']};
            font-size: 15px;
            opacity: 0.95;
            font-weight: 450;
            letter-spacing: 0.4px;
        }}
    """

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