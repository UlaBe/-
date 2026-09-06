import sys
import threading
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.ui import Ui_MainWindow
import webbrowser
from app.videoHelper import StopRequested, start as start_video_helper
from app.login_dialog import LoginDialog


csrftoken = ""
sessionid = ""
university_id = ""


def resource_path(relative_path):
    """Return a path that works both in source and PyInstaller bundles."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base_path / relative_path)


def app_icon():
    return QIcon(resource_path("app/Maodie.ico"))


class HelpMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("帮助")
        self.setWindowIcon(app_icon())
        self.setIcon(QMessageBox.Information)

        self.label = QLabel()
        self.label.setText(
            "\n\n【方法一：一键获取（推荐）】\n"
            "点击「一键获取」按钮，会在软件内打开登录页面，\n"
            "扫码或输入账号密码登录后自动提取参数。\n\n"
            "【方法二：手动填写】\n"
            "浏览器登录上雨课堂，然后按 F12 --> 选 Application --> 找到雨课堂的 cookies，"
            "寻找 csrftoken、sessionid、\n\nuniversity_id 字段\n\n"
            "如果出现报错可以尝试关闭代理\n\n"
            "遇到问题请在 GitHub Issues 提交反馈\n\n"
            "项目源码/使用教程："
        )

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText("https://github.com/UlaBe/yuketangHelperSCUT")
        self.text_edit.setReadOnly(True)
        self.text_edit.setFixedHeight(30)

        layout = self.layout()
        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.text_edit, 1, 0)


class VideoHelperThread(QThread):
    output_signal = pyqtSignal(str)
    input_requested = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, csrftoken, sessionid, university_id):
        super().__init__()
        self.csrftoken = csrftoken
        self.sessionid = sessionid
        self.university_id = university_id
        self._is_running = True
        self._input_event = threading.Event()
        self._input_value = None

    def run(self):
        try:
            start_video_helper(
                self.csrftoken,
                self.sessionid,
                self.university_id,
                log_callback=self.output_signal.emit,
                input_callback=self.request_input,
                stop_callback=self.should_stop,
            )
        except StopRequested:
            self.output_signal.emit("任务已停止")
        except Exception as e:
            self.output_signal.emit(f"运行时发生错误: {str(e)}")
        finally:
            self.finished_signal.emit()

    def should_stop(self):
        return not self._is_running

    def request_input(self, prompt):
        self._input_value = None
        self._input_event.clear()
        self.input_requested.emit(prompt)
        while self._is_running:
            if self._input_event.wait(0.1):
                if self._input_value is None:
                    raise StopRequested("任务已停止")
                return self._input_value
        raise StopRequested("任务已停止")

    def send_user_input(self, user_input):
        self._input_value = user_input
        self._input_event.set()

    def stop(self):
        self._is_running = False
        self._input_event.set()


class InputDialog(QDialog):
    input_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("输入课程编号")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)

        layout = QVBoxLayout()

        self.label = QLabel("请输入课程编号:")
        layout.addWidget(self.label)

        self.input_field = QLineEdit(self)
        self.input_field.returnPressed.connect(self.submit_input)
        layout.addWidget(self.input_field)

        self.submit_button = QPushButton("提交", self)
        self.submit_button.clicked.connect(self.submit_input)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def open_for_prompt(self, prompt):
        self.label.setText(prompt)
        self.input_field.clear()
        self.adjustSize()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_field.setFocus()

    def submit_input(self):
        user_input = self.input_field.text().strip()
        self.input_signal.emit(user_input)
        self.close()


class mywindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(mywindow, self).__init__()
        self.setupUi(self)
        self.setWindowIcon(app_icon())

        self.start.clicked.connect(self.startprocess)
        self.stop.clicked.connect(self.stopprocess)
        self.help.clicked.connect(self.show_help)
        self.auto_fetch.clicked.connect(self.auto_fetch_cookies)
        self.go_web.clicked.connect(self.open_website)
        self.sub_thread = None
        self.input_dialog = InputDialog(self)
        self.input_dialog.input_signal.connect(self.send_input_to_worker)
        self.stop.setEnabled(False)

        self.auto_scroll = True
        self.textBrowser.verticalScrollBar().valueChanged.connect(self.check_scroll_position)

    def startprocess(self):
        global csrftoken, sessionid, university_id
        csrftoken = self.csrftoken_input.toPlainText().strip()
        sessionid = self.sessionid_input.toPlainText().strip()
        university_id = self.university_id_input.toPlainText().strip()

        if not csrftoken or not sessionid or not university_id:
            QMessageBox.critical(self, "错误", "参数不能为空！")
            return
        if self.sub_thread and self.sub_thread.isRunning():
            QMessageBox.information(self, "提示", "任务正在运行中")
            return

        self.sub_thread = VideoHelperThread(csrftoken, sessionid, university_id)
        self.sub_thread.output_signal.connect(self.update_text_browser)
        self.sub_thread.input_requested.connect(self.handle_input_request)
        self.sub_thread.finished_signal.connect(self.handle_task_finished)
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.sub_thread.start()

    def stopprocess(self):
        if self.sub_thread and self.sub_thread.isRunning():
            self.sub_thread.stop()
            self.textBrowser.append("正在停止刷课任务...")

    def update_text_browser(self, text):
        self.textBrowser.append(text)
        if self.auto_scroll:
            QTimer.singleShot(0, self.textBrowser.ensureCursorVisible)

    def handle_input_request(self, prompt):
        self.update_text_browser("请选择要刷的课程编号")
        self.input_dialog.open_for_prompt(prompt)

    def send_input_to_worker(self, user_input):
        if self.sub_thread:
            self.sub_thread.send_user_input(user_input)
        self.auto_scroll = True

    def handle_task_finished(self):
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.sub_thread = None

    def show_help(self):
        help_box = HelpMessageBox(self)
        help_box.exec_()

    def check_scroll_position(self, value):
        scrollbar = self.textBrowser.verticalScrollBar()
        self.auto_scroll = value >= scrollbar.maximum() - 5

    def auto_fetch_cookies(self):
        """打开内嵌浏览器登录对话框，登录成功后自动提取参数。"""
        self.textBrowser.append("=" * 50)
        self.textBrowser.append("打开登录窗口，请在窗口内登录雨课堂...")

        login_dialog = LoginDialog(self)
        if login_dialog.exec_() == QDialog.Accepted:
            cookies = login_dialog.get_cookies()
            self.on_cookies_fetched(cookies)
        else:
            self.textBrowser.append("已取消登录")
            self.textBrowser.append("=" * 50)

    def on_cookies_fetched(self, cookies):
        """Handle successfully fetched cookies."""
        csrftoken = cookies.get("csrftoken", "")
        sessionid = cookies.get("sessionid", "")
        university_id = cookies.get("university_id", "")

        # Fill in the input fields
        self.csrftoken_input.setPlainText(csrftoken)
        self.sessionid_input.setPlainText(sessionid)
        self.university_id_input.setPlainText(university_id)

        self.textBrowser.append("[OK] 参数已自动填充到对应输入框！")
        self.textBrowser.append("请点击「启动」开始刷课")
        self.textBrowser.append("=" * 50)

    def open_website(self):
        webbrowser.open("https://scut.yuketang.cn/pro/courselist")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    window = mywindow()
    window.show()
    sys.exit(app.exec_())
