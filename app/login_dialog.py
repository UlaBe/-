# -*- coding: utf-8 -*-
"""
内置浏览器登录对话框 - 使用 QWebEngineView 在软件内嵌浏览器登录雨课堂。
用户登录后自动从 WebView 的 cookie store 提取参数，无需外部浏览器/ChromeDriver。
"""
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile


YUKETANG_COURSE_LIST = "https://scut.yuketang.cn/pro/courselist"
REQUIRED_COOKIES = ["csrftoken", "sessionid", "university_id", "uv_id"]


class LoginDialog(QDialog):
    """内嵌浏览器登录对话框，登录成功后自动提取 cookies 并关闭。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录雨课堂（登录成功后自动关闭）")
        self.resize(900, 700)
        self.setMinimumSize(700, 550)

        self._cookies = {}
        self._login_detected = False
        self._check_count = 0

        # 浏览器占满整个窗口
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.webview = QWebEngineView(self)
        # 缩小页面，让登录按钮完整显示，避免滚动
        self.webview.setZoomFactor(0.75)
        layout.addWidget(self.webview, 1)

        # 获取默认 profile（所有 WebView 共享），监听 cookie
        profile = QWebEngineProfile.defaultProfile()
        self.cookie_store = profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self._on_cookie_added)

        # 监听页面加载
        self.webview.loadStarted.connect(
            lambda: self.setWindowTitle("加载中... 登录雨课堂")
        )
        self.webview.loadFinished.connect(self._on_load_finished)

        # 加载雨课堂课程列表页（未登录会自动跳转到登录页）
        self.webview.load(QUrl(YUKETANG_COURSE_LIST))

    def _on_cookie_added(self, cookie):
        """收集所有 cookie，sessionid 出现时触发登录检测。"""
        try:
            name = str(cookie.name(), encoding="utf-8", errors="ignore")
            value = str(cookie.value(), encoding="utf-8", errors="ignore")
            if name in REQUIRED_COOKIES:
                self._cookies[name] = value
                # sessionid 被设置说明登录成功了
                if name == "sessionid" and value and not self._login_detected:
                    self._login_detected = True
                    self.setWindowTitle("检测到登录成功，正在提取参数...")
                    QTimer.singleShot(1000, self._check_login)
        except Exception:
            pass

    def _on_load_finished(self, ok):
        self.setWindowTitle("登录雨课堂（登录成功后自动关闭）")
        if ok:
            # 页面加载完成后，主动加载所有 cookies（触发 cookieAdded 回调）
            self.cookie_store.loadAllCookies()
            # 检查是否已经登录（例如之前登录过，cookies 已持久化）
            QTimer.singleShot(800, self._check_login)

    def _check_login(self):
        """检查是否已获取到所有必要 cookies，是则关闭对话框。"""
        csrftoken = self._cookies.get("csrftoken", "")
        sessionid = self._cookies.get("sessionid", "")
        university_id = self._cookies.get("university_id", "") or self._cookies.get("uv_id", "")

        if csrftoken and sessionid and university_id:
            # 三个参数齐全，成功
            self.accept()
        elif csrftoken and sessionid and self._login_detected:
            # 有 csrftoken 和 sessionid 但缺 university_id，再等待重试
            self._check_count += 1
            if self._check_count > 10:
                # 等了太久还没拿到 university_id，用空值先返回（提示用户手动补）
                self.accept()
            else:
                self.cookie_store.loadAllCookies()
                QTimer.singleShot(1000, self._check_login)

    def get_cookies(self):
        """返回提取到的 cookies 字典。"""
        return {
            "csrftoken": self._cookies.get("csrftoken", ""),
            "sessionid": self._cookies.get("sessionid", ""),
            "university_id": (
                self._cookies.get("university_id", "")
                or self._cookies.get("uv_id", "")
            ),
        }
