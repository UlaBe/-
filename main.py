import sys
import os

# 必须在 QApplication 创建之前设置：禁用 GPU 硬件加速，修复页面渲染问题
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from app.gui_runexe import mywindow
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from app.gui_runexe import resource_path

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(resource_path("app/Maodie.ico")))
window = mywindow()
window.show()
sys.exit(app.exec_())
