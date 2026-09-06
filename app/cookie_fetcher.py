# -*- coding: utf-8 -*-
"""
Auto cookie fetcher - uses Selenium to open a browser window,
let the user log in to yuketang, then auto-extract cookies.
"""
import time


class CookieFetcher:
    """Opens a browser window for user login, extracts cookies after login."""

    YUKETANG_URL = "https://scut.yuketang.cn/"
    COURSE_LIST_URL = "https://scut.yuketang.cn/pro/courselist"
    # 登录入口就是课程列表页，未登录会自动跳转到登录页
    LOGIN_URL = "https://scut.yuketang.cn/pro/courselist"

    # Cookies we need to extract
    REQUIRED_COOKIES = ["csrftoken", "sessionid", "university_id", "platform_id"]

    def __init__(self, log_callback=None, stop_callback=None):
        self.log = log_callback or (lambda msg: print(msg, flush=True))
        self.stop_callback = stop_callback or (lambda: False)
        self._driver = None
        self._fetched_cookies = {}

    def _check_stop(self):
        if self.stop_callback():
            raise Exception("用户取消了操作")

    def _ensure_webdriver(self):
        """Lazy-import selenium and ensure webdriver is available."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
        except ImportError:
            raise ImportError(
                "需要安装 selenium 包。请运行: pip install selenium\n"
                "同时也需要 webdriver-manager: pip install webdriver-manager"
            )

        # Try to auto-manage chromedriver
        try:
            from webdriver_manager.chrome import ChromeDriverManager

            service = Service(ChromeDriverManager().install())
        except ImportError:
            # Try system chromedriver
            service = Service()

        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        # Don't use headless - user needs to log in manually
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("detach", False)

        driver = webdriver.Chrome(service=service, options=options)
        return driver

    def fetch_cookies(self):
        """
        Open browser, let user log in, extract cookies.
        Returns dict with csrftoken, sessionid, university_id.
        Blocks until login is complete or user stops.
        """
        self.log("正在启动浏览器，请在新打开的浏览器窗口中登录雨课堂...")

        driver = self._ensure_webdriver()
        self._driver = driver

        try:
            # Navigate to yuketang course list page (auto-redirects to login if needed)
            driver.get(self.LOGIN_URL)
            self.log("已打开雨课堂页面（未登录会自动跳转到登录页）")
            self.log("请在浏览器中完成登录（微信扫码或账号密码）")
            self.log("登录成功后脚本将自动获取参数...")

            # Wait for the user to log in by polling for cookies
            cookies = self._wait_for_login(driver)

            # After login detected, navigate to course list to get final valid cookies
            try:
                driver.get(self.COURSE_LIST_URL)
                time.sleep(3)
                final_cookies = driver.get_cookies()
                final_dict = {c["name"]: c["value"] for c in final_cookies}
                # Update with the freshest cookie values
                for key in ("csrftoken", "sessionid", "university_id", "uv_id"):
                    if final_dict.get(key):
                        cookies[key] = final_dict[key]
                self.log("已刷新登录后的最新cookies")
            except Exception as e:
                self.log(f"刷新cookies时出错（不影响使用）: {e}")

            self._fetched_cookies = cookies
            self.log("[OK] 成功获取登录参数！")
            self.log(f"  csrftoken: {cookies.get('csrftoken', 'N/A')[:20]}...")
            self.log(f"  sessionid: {cookies.get('sessionid', 'N/A')[:20]}...")
            self.log(f"  university_id: {cookies.get('university_id', 'N/A')}")

            return cookies

        except Exception as e:
            self.log(f"获取参数失败: {e}")
            raise
        finally:
            try:
                driver.quit()
            except Exception:
                pass
            self._driver = None

    def _wait_for_login(self, driver, timeout=300):
        """
        Wait for user to log in. Check cookies periodically.
        Returns the required cookies once detected.
        Times out after `timeout` seconds (default 5 minutes).
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            self._check_stop()

            # Get all cookies from the browser
            try:
                all_cookies = driver.get_cookies()
            except Exception:
                time.sleep(1)
                continue

            # Build a lookup dict
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}

            # Check if we have all required cookies
            has_csrftoken = bool(cookie_dict.get("csrftoken"))
            has_sessionid = bool(cookie_dict.get("sessionid"))
            has_university_id = (
                bool(cookie_dict.get("university_id"))
                or bool(cookie_dict.get("uv_id"))
            )

            # Check if we're on the course list page (indicates login success)
            current_url = driver.current_url
            on_course_page = "courselist" in current_url or "pro/portal" in current_url

            if has_csrftoken and has_sessionid and (has_university_id or on_course_page):
                # Debug: print full cookie info including domain/path
                self.log("登录成功！提取到的cookies详细信息:")
                for c in all_cookies:
                    self.log(
                        f"  {c.get('name')} = {str(c.get('value'))[:30]}... "
                        f"domain={c.get('domain')} path={c.get('path')} "
                        f"secure={c.get('secure')} httpOnly={c.get('httpOnly')}"
                    )

                # If university_id is missing but we're logged in, try to get it from other cookies
                university_id = cookie_dict.get("university_id") or cookie_dict.get("uv_id", "")

                result = {
                    "csrftoken": cookie_dict.get("csrftoken", ""),
                    "sessionid": cookie_dict.get("sessionid", ""),
                    "university_id": university_id,
                }

                # If university_id is still empty, try to visit a page that triggers it
                if not university_id and on_course_page:
                    try:
                        driver.get(self.COURSE_LIST_URL)
                        time.sleep(2)
                        all_cookies = driver.get_cookies()
                        cookie_dict2 = {c["name"]: c["value"] for c in all_cookies}
                        result["university_id"] = cookie_dict2.get(
                            "university_id", cookie_dict2.get("uv_id", "")
                        )
                    except Exception:
                        pass

                return result

            # Show waiting indicator every 5 seconds
            elapsed = int(time.time() - start_time)
            if elapsed % 5 == 0 and elapsed > 0:
                self.log(
                    f"等待登录中... (已等待 {elapsed} 秒) "
                    f"当前cookies: csrftoken={'OK' if has_csrftoken else '--'} "
                    f"sessionid={'OK' if has_sessionid else '--'}"
                )

            time.sleep(1)

        raise TimeoutError("登录超时（5分钟），请重试")


def fetch_cookies_sync(log_callback=None, stop_callback=None):
    """Synchronous wrapper for fetching cookies via browser window."""
    fetcher = CookieFetcher(log_callback=log_callback, stop_callback=stop_callback)
    return fetcher.fetch_cookies()
