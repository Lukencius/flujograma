from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QToolButton, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QMessageBox,
                             QPushButton, QInputDialog, QDialog, QDialogButtonBox, QProgressBar, QFormLayout,
                             QTableWidget, QTableWidgetItem, QComboBox, QFrame, QCalendarWidget, QProgressDialog,
                             QHeaderView, QCheckBox, QFileDialog, QAbstractItemView)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QDate, QByteArray
from PyQt6.QtGui import QIcon, QColor, QPixmap, QFont, QPainter
from PyQt6.QtSvg import QSvgRenderer  # Esta es la importación correcta
from PyQt6.QtCore import Qt, QByteArray
from io import BytesIO
import pymysql
import sys
import os
import time
import sqlite3
import hashlib
from io import BytesIO
import json
import os.path

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

# Definir los iconos SVG para el ojo
EYE_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"></path>
    <circle cx="12" cy="12" r="3"></circle>
</svg>
'''

EYE_OFF_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
    <line x1="1" y1="1" x2="23" y2="23"></line>
</svg>
'''

# Función para crear un icono desde SVG
def create_icon_from_svg(svg_content, color='white'):
    # Reemplazar el color en el SVG
    svg_content = svg_content.replace('currentColor', color)
    
    # Crear QPixmap
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    # Crear QIcon directamente desde el SVG como imagen
    icon = QIcon()
    icon.addPixmap(pixmap)
    
    return icon

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
    _connection_pool = None
    _max_retries = 3
    _retry_delay = 1  # segundos
    
    @classmethod
    def get_connection(cls):
        """Obtiene una conexión del pool"""
        if cls._connection_pool is None:
            cls._connection_pool = pymysql.connect(**DB_CONFIG)
        return cls._connection_pool

    @classmethod
    def execute_query(cls, query, params=None, retries=0):
        """Ejecuta una query con reintentos y manejo de errores mejorado"""
        try:
            connection = cls.get_connection()
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    return result
                    
                connection.commit()
                return cursor.rowcount
                
        except pymysql.Error as e:
            if retries < cls._max_retries:
                time.sleep(cls._retry_delay)
                return cls.execute_query(query, params, retries + 1)
            raise Exception(f"Error en la base de datos después de {cls._max_retries} intentos: {str(e)}")
            
        except Exception as e:
            raise Exception(f"Error inesperado: {str(e)}")

    @classmethod
    def batch_insert(cls, table, columns, values):
        """Inserta múltiples registros en una sola transacción"""
        try:
            placeholders = ', '.join(['%s'] * len(columns))
            query = f"""
                INSERT INTO {table} 
                ({', '.join(columns)}) 
                VALUES ({placeholders})
            """
            
            connection = cls.get_connection()
            with connection.cursor() as cursor:
                cursor.executemany(query, values)
                connection.commit()
                return cursor.rowcount
                
        except Exception as e:
            raise Exception(f"Error en inserción por lotes: {str(e)}")

    @classmethod
    def execute_transaction(cls, queries):
        """Ejecuta múltiples queries en una transacción"""
        connection = cls.get_connection()
        try:
            with connection.cursor() as cursor:
                for query, params in queries:
                    cursor.execute(query, params)
                connection.commit()
                
        except Exception as e:
            connection.rollback()
            raise Exception(f"Error en transacción: {str(e)}")

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
        self.setup_button_visibility()  # Añadir esta línea

    def setup_button_visibility(self):
        """Configura la visibilidad de los botones según el rol del usuario"""
        # Obtener todos los botones
        buttons = self.findChildren(QPushButton)
        
        # Mapeo de roles y sus permisos
        role_permissions = {
            "admin": ["Agregar Nuevo Documento", "Consultar Documento", 
                     "Eliminar Documento", "Modificar Documento", "Administrar"],
            "recepcionista": ["Agregar Nuevo Documento", "Consultar Documento"],
            "usuario": ["Consultar Documento"]
        }
        
        # Obtener los permisos para el rol actual
        allowed_buttons = role_permissions.get(self.user_role.lower(), [])
        
        # Añadir "Cerrar Sesión" a los botones permitidos para todos los roles
        allowed_buttons.append("Cerrar Sesión")
        
        # Configurar visibilidad de botones
        for button in buttons:
            if button.text() in allowed_buttons:
                button.setVisible(True)
            else:
                button.setVisible(False)

    def init_ui(self):
        self.setWindowTitle("Interfaz de Corporación Isla de Maipo")
        self.setGeometry(0, 0, 1920, 1080)
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
        scaled_pixmap = logo_pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
            ("Agregar Nuevo Documento", self.agregar_datos),
            ("Consultar Documento", self.consultar_datos),
            ("Eliminar Documento", self.eliminar_datos),
            ("Modificar Documento", self.modificar_datos),
            ("Administrar", self.show_admin_panel)
        ]

        for text, slot in buttons_data:
            btn = QPushButton(text)
            btn.setObjectName(text)  # Añadir esta línea para identificar el botón
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
        
        # Añadir botón para seleccionar PDF
        pdf_button = QPushButton("Seleccionar PDF")
        self.pdf_path = None  # Variable para almacenar la ruta del PDF
        
        def seleccionar_pdf():
            file_name, _ = QFileDialog.getOpenFileName(
                dialog,
                "Seleccionar PDF",
                "",
                "PDF Files (*.pdf)"
            )
            if file_name:
                self.pdf_path = file_name
                pdf_button.setText("PDF seleccionado ✓")
        
        pdf_button.clicked.connect(seleccionar_pdf)
        
        # Añadir el botón después del calendario
        layout.addRow("Archivo PDF:", pdf_button)

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
                # Leer el archivo PDF si fue seleccionado
                pdf_data = None
                if self.pdf_path:
                    with open(self.pdf_path, 'rb') as file:
                        pdf_data = file.read()
                
                # Obtener la fecha seleccionada en formato yyyy-mm-dd
                fecha_seleccionada = fecha_input.selectedDate().toString("yyyy-MM-dd")
                
                DatabaseManager.execute_query(
                    """INSERT INTO documento(
                        fecha, establecimiento, tipodocumento, 
                        nrodocumento, materia, destino, firma, estado,
                        archivo_pdf
                    ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (fecha_seleccionada),
                     inputs['establecimiento'].text(),
                     inputs['tipodocumento'].text(),
                     inputs['nrodocumento'].text(),
                     inputs['materia'].text(),
                     inputs['destino'].text(),
                     inputs['firma'].text(),
                     inputs['estado'].text(),
                     pdf_data)
                
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
                 data['estado']
                ))
            for entry in self.entries.values():
                entry.clear()
            
            self.mostrar_mensaje("Éxito", "Datos agregados exitosamente")
        except ValueError as e:
            self.mostrar_mensaje("Error de validación", str(e), QMessageBox.Icon.Warning)
        except Exception as e:
            self.mostrar_mensaje("Error inesperado", f"Ocurrió un error al guardar los datos: {str(e)}", QMessageBox.Icon.Critical)

    def consultar_datos(self):
        try:
            # Consulta SQL ordenada por ID descendente
            query = """
                SELECT 
                    id_documento,
                    fecha,
                    establecimiento,
                    tipodocumento,
                    nrodocumento,
                    materia,
                    destino,
                    firma,
                    estado,
                    CASE WHEN archivo_pdf IS NOT NULL THEN 1 ELSE 0 END as tiene_pdf
                FROM documento 
                ORDER BY id_documento DESC  # Ordenar por ID descendente
            """
            resultados = DatabaseManager.execute_query(query)
            
            # Limpiar el tree widget
            self.tree_widget.clear()
            
            # Configurar las columnas si no están configuradas
            if self.tree_widget.columnCount() != 10:  # 9 campos + columna PDF
                self.tree_widget.setHeaderLabels([
                    "ID", "Fecha", "Establecimiento", "Tipo Doc", 
                    "Nro Doc", "Materia", "Destino", "Firma", "Estado", "PDF"
                ])
            
            # Procesar cada resultado
            for registro in resultados:
                # Crear item
                item = QTreeWidgetItem()
                
                # Establecer los textos de las columnas
                for i, campo in enumerate(['id_documento', 'fecha', 'establecimiento', 
                                        'tipodocumento', 'nrodocumento', 'materia', 
                                        'destino', 'firma', 'estado']):
                    item.setText(i, str(registro[campo]))
                
                # Añadir el item al tree widget
                self.tree_widget.addTopLevelItem(item)
                
                # Crear widget contenedor para el botón PDF
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                
                # Crear botón PDF con tamaño más pequeño
                download_btn = QPushButton("📥")
                download_btn.setFixedSize(18, 18)
                download_btn.setToolTip("Descargar PDF")
                
                # Verificar si tiene PDF
                tiene_pdf = bool(registro['tiene_pdf'])
                download_btn.setEnabled(tiene_pdf)
                
                # Colores personalizados
                COLOR_PDF = "#FF8C00"  # Naranja
                COLOR_NO_PDF = "#808080"  # Gris
                COLOR_HOVER = "#FF6B00"  # Naranja más oscuro para hover
                
                # Estilo del botón con aura
                download_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLOR_PDF if tiene_pdf else COLOR_NO_PDF};
                        color: white;
                        border: none;
                        border-radius: 9px;
                        padding: 0px;
                        font-size: 10px;
                        qproperty-alignment: AlignCenter;
                        box-shadow: 0 0 5px {COLOR_PDF if tiene_pdf else COLOR_NO_PDF};  /* Aura normal */
                    }}
                    QPushButton:hover {{
                        background-color: {COLOR_HOVER if tiene_pdf else COLOR_NO_PDF};
                        box-shadow: 0 0 8px {COLOR_HOVER if tiene_pdf else COLOR_NO_PDF};  /* Aura más intensa en hover */
                    }}
                    QPushButton:disabled {{
                        background-color: {COLOR_NO_PDF};
                        color: #CCCCCC;
                        box-shadow: 0 0 5px {COLOR_NO_PDF};  /* Aura gris */
                    }}
                """)
                
                # Conectar el botón si tiene PDF
                if tiene_pdf:
                    doc_id = registro['id_documento']
                    download_btn.clicked.connect(
                        lambda checked, x=doc_id: self.descargar_pdf(x)
                    )
                
                # Añadir botón al layout y centrarlo
                layout.addWidget(download_btn, 0, Qt.AlignmentFlag.AlignCenter)
                
                # Establecer el widget en la última columna
                self.tree_widget.setItemWidget(item, 9, container)
            
            # Ajustar el ancho de la columna PDF específicamente
            self.tree_widget.setColumnWidth(9, 30)
            
            # Ajustar las demás columnas
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

    def _get_pdf_button_style(self, enabled):
        """Helper para el estilo del botón PDF"""
        return f"""
            QPushButton {{
                background-color: {COLORS['primary'] if enabled else COLORS['surface']};
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
                min-width: 30px;
                max-width: 30px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark'] if enabled else COLORS['surface']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_secondary']};
            }}
        """

    def descargar_pdf(self, id_documento):
        """Función para descargar el PDF asociado a un documento"""
        try:
            # Obtener el PDF de la base de datos
            result = DatabaseManager.execute_query(
                "SELECT archivo_pdf FROM documento WHERE id_documento = %s",
                (id_documento,)
            )
            
            if result and result[0]['archivo_pdf']:
                # Abrir diálogo para seleccionar ubicación de guardado
                file_name, _ = QFileDialog.getSaveFileName(
                    self,
                    "Guardar PDF",
                    f"documento_{id_documento}.pdf",
                    "PDF Files (*.pdf)"
                )
                
                if file_name:
                    # Guardar el PDF en el sistema de archivos
                    with open(file_name, 'wb') as file:
                        file.write(result[0]['archivo_pdf'])
                    
                    self.mostrar_mensaje(
                        "Éxito",
                        f"PDF guardado exitosamente en {file_name}"
                    )
            else:
                self.mostrar_mensaje(
                    "Error",
                    "No hay PDF asociado a este documento",
                    QMessageBox.Icon.Warning
                )
                
        except Exception as e:
            self.mostrar_mensaje(
                "Error",
                f"Error al descargar el PDF: {str(e)}",
                QMessageBox.Icon.Critical
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

        # Añadir botón para seleccionar PDF
        pdf_button = QPushButton("Seleccionar PDF")
        self.pdf_path = None  # Variable para almacenar la ruta del PDF
        
        def seleccionar_pdf():
            file_name, _ = QFileDialog.getOpenFileName(
                dialog,
                "Seleccionar PDF",
                "",
                "PDF Files (*.pdf)"
            )
            if file_name:
                self.pdf_path = file_name
                pdf_button.setText("PDF seleccionado ✓")
        
        pdf_button.clicked.connect(seleccionar_pdf)
        
        # Añadir el botón después del calendario
        layout.addRow("Archivo PDF:", pdf_button)

        # Obtener el PDF actual si existe
        try:
            result = DatabaseManager.execute_query(
                "SELECT archivo_pdf FROM documento WHERE id_documento = %s",
                (id_to_modify,)
            )
            if result and result[0]['archivo_pdf']:
                pdf_button.setText("PDF existente ✓ (Click para cambiar)")
        except Exception as e:
            print(f"Error al obtener PDF actual: {str(e)}")

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
                
                # Preparar la consulta SQL base
                query = """UPDATE documento SET 
                    fecha = %s, establecimiento = %s, tipodocumento = %s,
                    nrodocumento = %s, materia = %s, destino = %s,
                    firma = %s, estado = %s"""
                
                params = [
                    fecha_seleccionada,
                    inputs['establecimiento'].text(),
                    inputs['tipodocumento'].text(),
                    inputs['nrodocumento'].text(),
                    inputs['materia'].text(),
                    inputs['destino'].text(),
                    inputs['firma'].text(),
                    inputs['estado'].text()
                ]

                # Si hay un nuevo PDF, añadirlo a la actualización
                if self.pdf_path:
                    with open(self.pdf_path, 'rb') as file:
                        pdf_data = file.read()
                    query += ", archivo_pdf = %s"
                    params.append(pdf_data)
                
                # Añadir la condición WHERE
                query += " WHERE id_documento = %s"
                params.append(id_to_modify)

                # Ejecutar la consulta
                DatabaseManager.execute_query(query, params)
                
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
        """Maneja el cierre de la aplicación"""
        try:
            # Verificar si hay un worker activo
            if hasattr(self, 'worker') and self.worker is not None:
                # Detener el worker si está ejecutándose
                if self.worker.isRunning():
                    self.worker.terminate()
                    self.worker.wait()
            
            # Cerrar la conexión a la base de datos
            if hasattr(DatabaseManager, '_connection_pool') and DatabaseManager._connection_pool:
                DatabaseManager._connection_pool.close()
            
            # Guardar configuraciones
            self.save_window_state()
            
            # Aceptar el evento de cierre
            event.accept()
            
        except Exception as e:
            print(f"Error al cerrar la aplicación: {e}")
            event.accept()

    def perform_search(self):
        """Realizar búsqueda optimizada con agrupación automática"""
        search_text = self.search_bar.text().strip().lower()
        search_field = self.search_combo.currentText()
        
        try:
            # Construir query base
            query = """
                SELECT d.*, EXTRACT(YEAR FROM fecha) as año,
                archivo_pdf IS NOT NULL as tiene_pdf 
                FROM documento d
                WHERE 1=1
            """
            params = []
            
            # Añadir filtros según el campo seleccionado
            field_mapping = {
                "Fecha": "fecha",
                "Establecimiento": "establecimiento",
                "Tipo Documento": "tipodocumento",
                "Nro Documento": "nrodocumento",
                "Materia": "materia",
                "Destino": "destino",
                "Firma": "firma",
                "Estado": "estado"
            }
            
            if search_text:
                if search_field == "Todos los campos":
                    conditions = []
                    for field in field_mapping.values():
                        conditions.append(f"LOWER(CAST({field} AS TEXT)) LIKE %s")
                        params.append(f"%{search_text}%")
                    query += f" AND ({' OR '.join(conditions)})"
                else:
                    field = field_mapping.get(search_field)
                    if field:
                        query += f" AND LOWER(CAST({field} AS TEXT)) LIKE %s"
                        params.append(f"%{search_text}%")
            
            query += " ORDER BY fecha DESC, id_documento DESC"
            
            resultados = DatabaseManager.execute_query(query, params)
            
            # Limpiar y preparar TreeWidget
            self.tree_widget.clear()
            grupos_año = {}
            
            # Agrupar resultados
            for registro in resultados:
                año = registro['año'] or 'Sin Año'
                estado = registro['estado'] or 'Sin Estado'
                
                if año not in grupos_año:
                    grupos_año[año] = {'estados': {}}
                
                if estado not in grupos_año[año]['estados']:
                    grupos_año[año]['estados'][estado] = []
                
                grupos_año[año]['estados'][estado].append(registro)
            
            # Mostrar resultados agrupados
            total_registros = 0
            for año in sorted(grupos_año.keys(), reverse=True):
                año_item = QTreeWidgetItem(self.tree_widget)
                año_item.setText(0, f"▼ Año {año}")
                
                # Estilo para grupo de año
                for col in range(self.tree_widget.columnCount()):
                    año_item.setBackground(col, QColor(COLORS['primary_dark']))
                    font = año_item.font(col)
                    font.setBold(True)
                    año_item.setFont(col, font)
                
                estados = grupos_año[año]['estados']
                for estado, registros in estados.items():
                    estado_item = QTreeWidgetItem(año_item)
                    estado_item.setText(0, f"▼ {estado} ({len(registros)})")
                    estado_item.setExpanded(True)
                    
                    # Estilo para subgrupo
                    for col in range(self.tree_widget.columnCount()):
                        estado_item.setBackground(col, QColor(COLORS['surface']))
                        estado_item.setFont(col, año_item.font(col))
                    
                    # Agregar registros
                    for reg in registros:
                        item = QTreeWidgetItem(estado_item)
                        campos = ['id_documento', 'fecha', 'establecimiento', 
                                'tipodocumento', 'nrodocumento', 'materia', 
                                'destino', 'firma', 'estado']
                        
                        for i, campo in enumerate(campos):
                            item.setText(i, str(reg[campo]))
                        total_registros += 1
            
            # Ajustar columnas y mostrar mensaje
            for i in range(self.tree_widget.columnCount()):
                self.tree_widget.resizeColumnToContents(i)
            
            mensaje = (f"Se encontraron {total_registros} registros" + 
                      (f" que coinciden con '{search_text}'" if search_text else ""))
            
            QMessageBox.information(self, "Resultados", mensaje)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error en la búsqueda: {str(e)}")

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

    def show_data_entry(self):
        """Mostrar el diálogo de ingreso de datos"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Agregar Documento")
        dialog.setFixedSize(800, 600)
        
        # Layout principal
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Panel superior (como en la ventana principal)
        top_panel = QWidget()
        top_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['surface']};
                border-radius: 10px;
            }}
        """)
        top_layout = QVBoxLayout(top_panel)
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(20, 20, 20, 20)

        # Título con ícono
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        icon_label.setPixmap(icon_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(icon_label)

        title_label = QLabel("Agregar Documento")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 24px;
                font-weight: bold;
            }}
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        top_layout.addLayout(header_layout)

        # Panel principal (como en la ventana principal)
        main_panel = QWidget()
        main_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['surface']};
                border-radius: 10px;
            }}
        """)
        form_layout = QFormLayout(main_panel)
        form_layout.setSpacing(15)
        form_layout.setContentsMargins(20, 20, 20, 20)

        # Estilo común para los campos de entrada
        input_style = f"""
            QLineEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: none;
                border-radius: 5px;
                padding: 10px;
                min-width: 300px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid {COLORS['primary']};
            }}
        """

        # Campos del formulario
        fields = {}
        field_names = ["Número", "Fecha", "Tipo", "Remitente", "Materia", "Destino", "Observaciones"]
        
        for field_name in field_names:
            label = QLabel(f"{field_name}:")
            label.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['text']};
                    font-size: 14px;
                    font-weight: bold;
                }}
            """)
            
            if field_name == "Fecha":
                widget = QCalendarWidget()
                widget.setStyleSheet(f"""
                    QCalendarWidget {{
                        background-color: {COLORS['background']};
                        color: {COLORS['text']};
                    }}
                    QCalendarWidget QToolButton {{
                        color: {COLORS['text']};
                        background-color: {COLORS['surface']};
                        border-radius: 5px;
                    }}
                    QCalendarWidget QToolButton:hover {{
                        background-color: {COLORS['primary']};
                    }}
                """)
            elif field_name == "Tipo":
                widget = QComboBox()
                widget.addItems(["Tipo 1", "Tipo 2", "Tipo 3"])
                widget.setStyleSheet(input_style)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText(f"Ingrese {field_name.lower()}")
                widget.setStyleSheet(input_style)
                if field_name == "Observaciones":
                    widget.setMinimumHeight(100)

            fields[field_name] = widget
            form_layout.addRow(label, widget)

        main_layout.addWidget(top_panel)
        main_layout.addWidget(main_panel)

        # Panel de botones
        button_panel = QWidget()
        button_layout = QHBoxLayout(button_panel)
        button_layout.setSpacing(15)
        button_layout.addStretch()

        # Botones con el mismo estilo que la aplicación principal
        cancel_button = QPushButton("Cancelar")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 2px solid {COLORS['error']};
                padding: 12px 30px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['error']};
            }}
        """)
        cancel_button.clicked.connect(dialog.reject)

        save_button = QPushButton("Guardar")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
                border: none;
                padding: 12px 30px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_dark']};
            }}
        """)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        main_layout.addWidget(button_panel)

        # Estilo general del diálogo
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
        """)
        
        dialog.exec()

import json
import os

class CredentialManager:
    CACHE_FILE = 'credentials_cache.json'
    
    @classmethod
    def save_credentials(cls, username, password, remember=True):
        """Guarda las credenciales del usuario tal cual las ingresó"""
        try:
            if not remember:
                cls.clear_credentials()
                return
                
            data = {
                'username': username,
                'password': password
            }
            
            with open(cls.CACHE_FILE, 'w') as f:
                json.dump(data, f)
                
        except Exception as e:
            print(f"Error al guardar credenciales: {e}")

    @classmethod
    def load_credentials(cls):
        """Carga las credenciales guardadas"""
        try:
            if not os.path.exists(cls.CACHE_FILE):
                return None
                
            with open(cls.CACHE_FILE, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"Error al cargar credenciales: {e}")
            return None

    @classmethod
    def clear_credentials(cls):
        """Elimina el archivo de credenciales"""
        try:
            if os.path.exists(cls.CACHE_FILE):
                os.remove(cls.CACHE_FILE)
        except Exception as e:
            print(f"Error al eliminar credenciales: {e}")

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inicio de Sesin - Corporación Isla de Maipo")
        self.setFixedWidth(550)
        self.setFixedHeight(650)  # Aumentado de 500 a 650
        self.user_role = None
        self.setup_ui()
        
        # Cargar credenciales guardadas
        saved_credentials = CredentialManager.load_credentials()
        if saved_credentials:
            self.username_input.setText(saved_credentials['username'])
            self.password_input.setText(saved_credentials['password'])
            self.remember_checkbox.setChecked(True)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        scaled_pixmap = logo_pixmap.scaled(360, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
        # Conectar el evento returnPressed
        self.username_input.returnPressed.connect(self.login)

        # Contenedor para el campo de contraseña
        password_container = QWidget()
        password_layout = QHBoxLayout(password_container)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(5)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Ingrese su contraseña")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(create_input_style())
        self.password_input.setMinimumHeight(42)
        self.password_input.setFont(QFont("Segoe UI", 14))
        # Conectar el evento returnPressed
        self.password_input.returnPressed.connect(self.login)
        password_layout.addWidget(self.password_input)

        # Botón mostrar/ocultar contraseña
        self.toggle_password_btn = QPushButton("🔒")  # Inicialmente cerrado
        self.toggle_password_btn.setFixedSize(35, 35)
        self.toggle_password_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_password_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 18px;
                color: {COLORS['text']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
            }}
        """)
        self.toggle_password_btn.clicked.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.toggle_password_btn)

        form_layout.addRow(self.create_label("Usuario:"), self.username_input)
        form_layout.addRow(self.create_label("Contraseña:"), password_container)

        main_layout.addWidget(form_widget)

        # Agregar checkbox "Recérdame" antes de los botones
        self.remember_checkbox = QCheckBox("Recordar mis datos")
        self.remember_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text']};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {COLORS['primary']};
                border-radius: 4px;
                background-color: {COLORS['surface']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['primary']};
                image: url(check.png);
            }}
            QCheckBox::indicator:hover {{
                border-color: {COLORS['primary_light']};
            }}
        """)
        main_layout.addWidget(self.remember_checkbox)

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
                self.show_custom_error(
                    "Campos Incompletos", 
                    "Por favor complete todos los campos para iniciar sesión.",
                    "Los campos de usuario y contraseña son obligatorios."
                )
                return
                
            success, role = DatabaseManager.validate_login(username, password)
            if success:
                self.user_role = role
                
                # Guardar credenciales si el checkbox está marcado
                if self.remember_checkbox.isChecked():
                    CredentialManager.save_credentials(
                        username, 
                        password, 
                        remember=True
                    )
                else:
                    CredentialManager.clear_credentials()
                
                self.accept()
            else:
                self.show_custom_error(
                    "Error de Autenticación", 
                    "No se pudo iniciar sesión con las credenciales proporcionadas.",
                    "Por favor verifique su usuario y contraseña."
                )
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

    def toggle_password_visibility(self):
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_password_btn.setText("🔓")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_password_btn.setText("🔒")

class RegisterDialog(QDialog):
    def __init__(self, parent=None, admin_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Registro de Usuario - Corporación Isla de Maipo")
        self.setFixedWidth(520)
        self.setFixedHeight(600)
        self.admin_mode = admin_mode
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("isla_de_maipo.png"))
        scaled_pixmap = logo_pixmap.scaled(170, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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

        # Botón mostrar/ocultar contraseña (inicialmente cerrado)
        self.toggle_password_btn = QPushButton("🔒")  # Candado cerrado inicial
        self.toggle_password_btn.setFixedSize(35, 35)
        self.toggle_password_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_password_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 18px;
                color: {COLORS['text']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
            }}
        """)
        self.toggle_password_btn.clicked.connect(self.toggle_password_visibility)
        buttons_layout.addWidget(self.toggle_password_btn)

        # Botón mostrar/ocultar confirmación (inicialmente cerrado)
        self.toggle_confirm_btn = QPushButton("🔒")  # Candado cerrado inicial
        self.toggle_confirm_btn.setFixedSize(35, 35)
        self.toggle_confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 18px;
                color: {COLORS['text']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
            }}
        """)
        self.toggle_confirm_btn.clicked.connect(self.toggle_confirm_visibility)
        buttons_layout.addWidget(self.toggle_confirm_btn)

        # Crear el botón de agregar datos con el nuevo estilo
        agregar_button = QToolButton()
        agregar_button.setText("Agregar Datos")
        agregar_button.setIcon(QIcon(resource_path("agregar.png")))  # Asegúrate de tener este ícono
        agregar_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        agregar_button.setStyleSheet("""
            QToolButton {
                background-color: """ + COLORS['surface'] + """;
                color: """ + COLORS['text'] + """;
                border: none;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
                min-width: 150px;
                margin: 5px;
                text-align: left;
            }
            QToolButton:hover {
                background-color: """ + COLORS['primary'] + """;
            }
            QToolButton:pressed {
                background-color: """ + COLORS['primary_dark'] + """;
            }
        """)
        agregar_button.setCursor(Qt.CursorShape.PointingHandCursor)
        agregar_button.clicked.connect(self.show_data_entry)

        # Agregar el botón al layout de botones
        self.buttons_layout.addWidget(agregar_button)

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

    def toggle_password_visibility(self):
        """Alternar visibilidad de la contraseña"""
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_password_btn.setText("🔓")  # Candado abierto
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_password_btn.setText("🔒")  # Candado cerrado

    def toggle_confirm_visibility(self):
        """Alternar visibilidad de la confirmación de contraseña"""
        if self.confirm_password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_confirm_btn.setText("🔓")  # Candado abierto
        else:
            self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_confirm_btn.setText("🔒")  # Candado cerrado

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
    """Crea el estilo común para los campos de entrada"""
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
            font-size: 13px;
            opacity: 0.7;
        }}
    """

def create_button_style():
    """Crea el estilo común para los botones"""
    return f"""
        QPushButton {{
            background-color: {COLORS['primary']};
            color: {COLORS['text']};
            border: none;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            min-width: 100px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['primary_dark']};
        }}
        QPushButton:pressed {{
            background-color: {COLORS['primary']};
        }}
        QPushButton:disabled {{
            background-color: {COLORS['surface']};
            color: {COLORS['text_secondary']};
        }}
    """

def create_label_style():
    """Crea el estilo común para las etiquetas"""
    return f"""
        QLabel {{
            color: {COLORS['text']};
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
    """

class PDFManager:
    CHUNK_SIZE = 8192  # 8KB chunks para lectura/escritura
    
    @staticmethod
    def save_pdf(id_documento, pdf_data):
        """Guarda un PDF en la base de datos de forma optimizada"""
        try:
            query = """
                UPDATE documento 
                SET archivo_pdf = %s 
                WHERE id_documento = %s
            """
            DatabaseManager.execute_query(query, (pdf_data, id_documento))
            
        except Exception as e:
            raise Exception(f"Error guardando PDF: {str(e)}")

    @staticmethod
    def get_pdf(id_documento):
        """Obtiene un PDF de la base de datos de forma optimizada"""
        try:
            query = """
                SELECT archivo_pdf 
                FROM documento 
                WHERE id_documento = %s 
                AND archivo_pdf IS NOT NULL
            """
            result = DatabaseManager.execute_query(query, (id_documento,))
            
            if not result:
                raise ValueError("PDF no encontrado")
                
            return result[0]['archivo_pdf']
            
        except Exception as e:
            raise Exception(f"Error obteniendo PDF: {str(e)}")

    @staticmethod
    def save_pdf_to_file(pdf_data, file_path):
        """Guarda un PDF en el sistema de archivos de forma optimizada"""
        try:
            with open(file_path, 'wb') as f:
                for i in range(0, len(pdf_data), PDFManager.CHUNK_SIZE):
                    chunk = pdf_data[i:i + PDFManager.CHUNK_SIZE]
                    f.write(chunk)
                    
        except Exception as e:
            raise Exception(f"Error guardando PDF en archivo: {str(e)}")

class UIManager:
    # Cache para estilos y fuentes
    _style_cache = {}
    _font_cache = {}
    
    @classmethod
    def get_style(cls, key, params=None):
        """Obtiene estilos cacheados para mejor rendimiento"""
        cache_key = f"{key}_{str(params)}"
        if cache_key not in cls._style_cache:
            cls._style_cache[cache_key] = cls._generate_style(key, params)
        return cls._style_cache[cache_key]

    @classmethod
    def get_font(cls, size, bold=False):
        """Obtiene fuentes cacheadas"""
        cache_key = f"{size}_{bold}"
        if cache_key not in cls._font_cache:
            font = QFont("Segoe UI", size)
            font.setBold(bold)
            cls._font_cache[cache_key] = font
        return cls._font_cache[cache_key]

    @staticmethod
    def create_button(text, icon_path=None, tooltip=None):
        """Crea botones con estilo consistente"""
        button = QPushButton(text)
        if icon_path:
            button.setIcon(QIcon(resource_path(icon_path)))
        if tooltip:
            button.setToolTip(tooltip)
        button.setStyleSheet(UIManager.get_style('button'))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    @staticmethod
    def create_tree_widget(headers):
        """Crea un TreeWidget optimizado"""
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setAlternatingRowColors(True)
        tree.setStyleSheet(UIManager.get_style('tree'))
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setSortingEnabled(True)
        return tree

    @staticmethod
    def _generate_style(key, params=None):
        """Genera estilos según el tipo de widget"""
        styles = {
            'button': f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: {COLORS['text']};
                    border: none;
                    padding: 10px;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_dark']};
                }}
                QPushButton:pressed {{
                    background-color: {COLORS['primary']};
                }}
            """,
            'tree': f"""
                QTreeWidget {{
                    background-color: {COLORS['surface']};
                    border: none;
                    border-radius: 8px;
                }}
                QTreeWidget::item {{
                    padding: 5px;
                    border-bottom: 1px solid {COLORS['primary']};
                }}
                QTreeWidget::item:selected {{
                    background-color: {COLORS['primary']};
                    color: {COLORS['text']};
                }}
            """
        }
        return styles.get(key, "")

class SignalManager(QObject):
    # Señales personalizadas
    data_updated = pyqtSignal()
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def emit_data_updated(cls):
        """Emite señal de actualización de datos"""
        if cls._instance:
            cls._instance.data_updated.emit()

    @classmethod
    def emit_error(cls, message):
        """Emite señal de error"""
        if cls._instance:
            cls._instance.error_occurred.emit(message)

    @classmethod
    def emit_progress(cls, value):
        """Emite señal de progreso"""
        if cls._instance:
            cls._instance.progress_updated.emit(value)

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