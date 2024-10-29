import sys
from PyQt6.QtWidgets import QApplication
from funciones import MainWindow

def main():
    app = QApplication(sys.argv)
    ventana_principal = MainWindow()
    ventana_principal.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
