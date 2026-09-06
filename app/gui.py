import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from app.gui_runexe import mywindow, resource_path


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("app/Maodie.ico")))
    window = mywindow()
    window.show()
    sys.exit(app.exec_())
