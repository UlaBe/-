# -*- coding: utf-8 -*-
# version 5
# developed by zk chen, refactored for in-process GUI usage

import argparse
import json
import random
import re
import time

import requests


URL_ROOT = "https://scut.yuketang.cn/"
LEARNING_RATE = 4
REQUEST_TIMEOUT = 30

LEAF_TYPE = {
    "video": 0,
    "homework": 6,
    "exam": 5,
    "recommend": 3,
    "discussion": 4,
}


class StopRequested(Exception):
    """Raised when the GUI asks the worker to stop."""


def make_headers(csrftoken, sessionid, university_id):
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "x-csrftoken": csrftoken,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "university-id": university_id,
        "xtbz": "cloud",
        "Referer": "https://scut.yuketang.cn/v2/web/studentLog/",
        "Origin": "https://scut.yuketang.cn",
    }


def make_cookies(csrftoken, sessionid, university_id):
    """Build a cookie dict for requests (more reliable than Cookie header)."""
    return {
        "csrftoken": csrftoken,
        "sessionid": sessionid,
        "university_id": university_id,
        "platform_id": "3",
    }


def _default_log(message):
    print(message, flush=True)


def _default_input(prompt):
    return input(prompt)


class VideoHelper:
    def __init__(
        self,
        csrftoken,
        sessionid,
        university_id,
        log_callback=None,
        input_callback=None,
        stop_callback=None,
        url_root=URL_ROOT,
        learning_rate=LEARNING_RATE,
    ):
        self.csrftoken = csrftoken
        self.sessionid = sessionid
        self.university_id = university_id
        self.url_root = url_root
        self.learning_rate = learning_rate
        self.headers = make_headers(csrftoken, sessionid, university_id)
        self.cookies = make_cookies(csrftoken, sessionid, university_id)
        self.log_callback = log_callback or _default_log
        self.input_callback = input_callback or _default_input
        self.stop_callback = stop_callback
        self.submit_url = (
            self.url_root
            + "mooc-api/v1/lms/exercise/problem_apply/?term=latest&uv_id="
            + self.university_id
        )
        self.session = requests.Session()
        # Pre-seed session cookies for the yuketang domain (both host-only and parent)
        for name, value in self.cookies.items():
            self.session.cookies.set(name, value, domain="scut.yuketang.cn", path="/")
            self.session.cookies.set(name, value, domain=".yuketang.cn", path="/")

        # Debug: log what cookies will be sent
        self.log(f"Cookie准备就绪: csrftoken={csrftoken[:15]}... "
                 f"sessionid={sessionid[:15]}... "
                 f"university_id={university_id}")

    def log(self, message):
        self.log_callback(str(message))

    def check_stop(self):
        if self.stop_callback and self.stop_callback():
            raise StopRequested("任务已停止")

    def sleep(self, seconds):
        end_time = time.time() + seconds
        while time.time() < end_time:
            self.check_stop()
            time.sleep(min(0.2, end_time - time.time()))

    def get(self, url):
        self.check_stop()
        response = self.session.get(
            url=url,
            headers=self.headers,
            timeout=REQUEST_TIMEOUT,
        )
        self.check_stop()
        return response

    def post(self, url, **kwargs):
        self.check_stop()
        response = self.session.post(
            url=url,
            headers=self.headers,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        self.check_stop()
        return response

    def one_video_watcher(self, video_id, video_name, cid, user_id, classroomid, skuid):
        video_id = str(video_id)
        classroomid = str(classroomid)
        url = self.url_root + "video-log/heartbeat/"
        get_url = (
            self.url_root
            + "video-log/get_video_watch_progress/?cid="
            + str(cid)
            + "&user_id="
            + str(user_id)
            + "&classroom_id="
            + classroomid
            + "&video_type=video&vtype=rate&video_id="
            + video_id
            + "&snapshot=1&term=latest&uv_id="
            + self.university_id
        )
        progress = self.get(get_url)
        if_completed = "0"
        try:
            if_completed = re.search(r'"completed":(.+?),', progress.text).group(1)
        except Exception:
            pass

        if if_completed == "1":
            self.log(video_name + "已经学习完毕，跳过")
            return 1

        self.log(video_name + "，尚未学习，现在开始自动学习")
        self.sleep(2)

        video_frame = 0
        val = 0
        try:
            res_rate = json.loads(progress.text)
            tmp_rate = res_rate["data"][video_id]["rate"]
            if tmp_rate is None:
                return 0
            val = tmp_rate
            video_frame = res_rate["data"][video_id]["watch_length"]
        except Exception as e:
            self.log(e)

        timestamp = int(round(time.time() * 1000))
        heart_data = []
        while float(val) <= 0.95:
            self.check_stop()
            for i in range(3):
                heart_data.append(
                    {
                        "i": 5,
                        "et": "loadeddata",
                        "p": "web",
                        "n": "ali-cdn.xuetangx.com",
                        "lob": "cloud4",
                        "cp": video_frame,
                        "fp": 0,
                        "tp": 0,
                        "sp": 2,
                        "ts": str(timestamp),
                        "u": int(user_id),
                        "uip": "",
                        "c": cid,
                        "v": int(video_id),
                        "skuid": skuid,
                        "classroomid": classroomid,
                        "cc": video_id,
                        "d": 4976.5,
                        "pg": video_id
                        + "_"
                        + "".join(
                            random.sample("zyxwvutsrqponmlkjihgfedcba1234567890", 4)
                        ),
                        "sq": i,
                        "t": "video",
                    }
                )
                video_frame += self.learning_rate

            data = {"heart_data": heart_data}
            response = self.post(url, json=data)
            heart_data = []

            try:
                delay_time = re.search(
                    r"Expected available in(.+?)second.", response.text
                ).group(1).strip()
                self.log("由于网络阻塞，万恶的雨课堂，要阻塞" + str(delay_time) + "秒")
                self.sleep(float(delay_time) + 0.5)
                self.log("恢复工作啦～～")
                self.post(self.submit_url, data=data)
            except Exception:
                pass

            try:
                progress = self.get(get_url)
                res_rate = json.loads(progress.text)
                tmp_rate = res_rate["data"][video_id]["rate"]
                if tmp_rate is None:
                    return 0
                val = str(tmp_rate)
                moment = f"{float(val) * 100:.2f}%"
                self.log("学习进度为：\t" + moment + "%/100%")
                self.sleep(2)
            except Exception as e:
                self.log(e)

        self.log("视频" + video_id + " " + video_name + "学习完成！")
        return 1

    def get_videos_ids(self, course_name, classroom_id, course_sign):
        get_homework_ids = (
            self.url_root
            + "mooc-api/v1/lms/learn/course/chapter?cid="
            + str(classroom_id)
            + "&term=latest&uv_id="
            + self.university_id
            + "&sign="
            + course_sign
        )
        homework_ids_response = self.get(get_homework_ids)
        text = homework_ids_response.text
        homework_dic = {}
        try:
            homework_json = json.loads(text)
            for chapter in homework_json["data"]["course_chapter"]:
                for section in chapter["section_leaf_list"]:
                    if "leaf_list" in section:
                        for leaf in section["leaf_list"]:
                            if leaf["leaf_type"] == LEAF_TYPE["video"]:
                                homework_dic[leaf["id"]] = leaf["name"]
                    elif section["leaf_type"] == LEAF_TYPE["video"]:
                        homework_dic[section["id"]] = section["name"]
            self.log(course_name + "共有" + str(len(homework_dic)) + "个视频喔！")
            return homework_dic
        except Exception as e:
            self.log("fail while getting homework_ids!!! please re-run this program!")
            self.log(f"响应内容前200字: {text[:200]}")
            raise Exception("获取视频列表失败！请重新点击「一键获取」获取最新参数后重试")

    def get_user_id(self):
        """Get user_id by trying multiple known yuketang APIs."""
        endpoints = [
            self.url_root + "edu_admin/check_user_session/",
            self.url_root + "v2/api/web/userinfo",
            self.url_root + "api/v3/user/basic-info",
        ]

        last_error = None
        for url in endpoints:
            try:
                name = url.split(self.url_root)[-1]
                self.log(f"尝试获取user_id: {name}")
                id_response = self.get(url)
                text = id_response.text
                self.log(f"  HTTP状态码: {id_response.status_code}")
                self.log(f"  响应内容: {text[:200]}")

                # Skip if it looks like an error page (HTML) or empty
                if not text or "<html" in text.lower():
                    last_error = f"接口返回异常内容: {text[:100]}"
                    continue

                # Try JSON parsing first
                try:
                    payload = json.loads(text)
                    user_id = self._extract_user_id_from_json(payload)
                    if user_id:
                        self.log(f"成功获取 user_id: {user_id}")
                        return user_id
                except Exception:
                    pass

                # Fall back to regex (supports both comma and brace terminators)
                m = re.search(r'"user_id"\s*:\s*"?(\d+)"?', text)
                if m:
                    user_id = m.group(1).strip()
                    self.log(f"成功获取 user_id: {user_id}")
                    return user_id

                last_error = f"响应中没有找到 user_id: {text[:100]}"

            except Exception as e:
                last_error = str(e)
                self.log(f"  请求异常: {e}")
                continue

        self.log("获取user_id失败，请确认cookie是否有效或重新获取参数")
        if last_error:
            self.log(f"详细信息: {last_error}")
        raise Exception("获取user_id失败！请重新点击「一键获取」获取最新参数，或检查网络后重试")

    def _extract_user_id_from_json(self, payload):
        """Recursively search a JSON payload for user_id."""
        if payload is None:
            return None
        if isinstance(payload, dict):
            for key in ("user_id", "userId", "uid", "id"):
                if key in payload and payload[key] is not None:
                    return str(payload[key]).strip()
            # Recursively search nested dicts
            for value in payload.values():
                result = self._extract_user_id_from_json(value)
                if result:
                    return result
        elif isinstance(payload, list):
            for item in payload:
                result = self._extract_user_id_from_json(item)
                if result:
                    return result
        return None

    def get_courses(self):
        """Get course list by trying multiple known yuketang APIs."""
        # Old API (mooc-api) first
        old_url = (
            self.url_root
            + "mooc-api/v1/lms/user/user-courses/?status=1&page=1&no_page=1"
            + "&term=latest&uv_id="
            + self.university_id
        )
        # New API (v2) as fallback
        new_url = self.url_root + "v2/api/web/courses/list?identity=2"

        endpoints = [old_url, new_url]
        last_error = None

        for url in endpoints:
            try:
                self.log(f"尝试获取课程列表: {url.split(self.url_root)[-1][:40]}")
                response = self.get(url)
                text = response.text

                if not text or "<html" in text.lower():
                    last_error = f"接口返回异常内容: {text[:100]}"
                    continue

                courses = self._parse_courses(text)
                if courses:
                    self.log(f"成功获取到 {len(courses)} 门课程")
                    return courses
                last_error = "接口返回中没有找到课程列表"
            except Exception as e:
                last_error = str(e)
                continue

        self.log("fail while getting classroom_id!!! please re-run this program!")
        if last_error:
            self.log(f"详细信息: {last_error}")
        raise Exception("获取课程列表失败！请重新点击「一键获取」获取最新参数，或检查网络后重试")

    def _parse_courses(self, text):
        """Parse course list from either old or new API response format."""
        courses = []
        try:
            payload = json.loads(text)
        except Exception:
            return courses

        data = payload.get("data", {})

        # New API format: data.list[].{classroom_id, course{name, id}, ...}
        if isinstance(data, dict) and "list" in data:
            for item in data["list"]:
                course = item.get("course", {})
                courses.append(
                    {
                        "course_name": course.get("name", item.get("name", "未知课程")),
                        "classroom_id": item.get("classroom_id"),
                        "course_sign": item.get("course_sign", ""),
                        "sku_id": item.get("sku_id", 0),
                        "course_id": course.get("id", item.get("id", 0)),
                    }
                )
            if courses:
                return courses

        # Old API format: data.product_list[].{course_name, classroom_id, ...}
        if isinstance(data, dict) and "product_list" in data:
            for course in data["product_list"]:
                courses.append(
                    {
                        "course_name": course.get("course_name", "未知课程"),
                        "classroom_id": course.get("classroom_id"),
                        "course_sign": course.get("course_sign", ""),
                        "sku_id": course.get("sku_id", 0),
                        "course_id": course.get("course_id", 0),
                    }
                )
            if courses:
                return courses

        return courses

    def ask_course_number(self, your_courses):
        prompt = "你想刷哪门课呢？请输入编号。输入0表示全部课程都刷一遍"
        while True:
            self.check_stop()
            number = self.input_callback(prompt)
            if number is None:
                raise StopRequested("任务已停止")

            number = str(number).strip()
            if not number.isdigit() or int(number) > len(your_courses):
                self.log("输入不合法！")
                continue
            return int(number)

    def start_watch(self):
        user_id = self.get_user_id()
        your_courses = self.get_courses()
        if not your_courses:
            self.log("没有获取到可学习的课程")
            return

        for index, value in enumerate(your_courses):
            self.log("编号：" + str(index + 1) + " 课名：" + str(value["course_name"]))

        number = self.ask_course_number(your_courses)
        if number == 0:
            courses_to_watch = your_courses
        else:
            courses_to_watch = [your_courses[number - 1]]

        for course in courses_to_watch:
            self.check_stop()
            homework_dic = self.get_videos_ids(
                course["course_name"],
                course["classroom_id"],
                course["course_sign"],
            )
            for one_video in homework_dic.items():
                self.one_video_watcher(
                    one_video[0],
                    one_video[1],
                    course["course_id"],
                    user_id,
                    course["classroom_id"],
                    course["sku_id"],
                )

        self.log("搞定啦")


def start(
    csrftoken,
    sessionid,
    university_id,
    log_callback=None,
    input_callback=None,
    stop_callback=None,
):
    helper = VideoHelper(
        csrftoken,
        sessionid,
        university_id,
        log_callback=log_callback,
        input_callback=input_callback,
        stop_callback=stop_callback,
    )
    helper.start_watch()


def main(argv=None):
    parser = argparse.ArgumentParser(description="自动刷雨课堂视频")
    parser.add_argument("--csrftoken", type=str, required=True, help="csrftoken")
    parser.add_argument("--sessionid", type=str, required=True, help="sessionid")
    parser.add_argument("--university_id", type=str, required=True, help="university_id")
    args = parser.parse_args(argv)

    start(args.csrftoken, args.sessionid, args.university_id)


if __name__ == "__main__":
    main()
