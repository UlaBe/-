import sys
from app.gui_runexe import mywindow
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from app.gui_runexe import resource_path

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(resource_path("app/Maodie.ico")))
window = mywindow()
window.show()
sys.exit(app.exec_())
