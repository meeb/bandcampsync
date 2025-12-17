from curl_cffi import requests
from .config import INTERNAL_USER_AGENT
from .logger import get_logger


log = get_logger("notify")


class NotifyURL:
    def __init__(self, notify_str):
        self.valid = False
        self.notify_str = notify_str
        self.method = "GET"
        self.url = ""
        self.headers = {}
        self.body = ""
        self.parse_notify_str()
        if self.valid:
            log.info(
                f"Notify created: {self.method} to {self.url} with headers: {list(self.headers.keys())}"
            )

    def parse_notify_str(self):
        if not self.notify_str:
            return
        parts = self.notify_str.split()
        if len(parts) == 1:
            self.url = parts[0]
            self.valid = True
            return
        elif len(parts) == 4:
            method = parts[0].upper()
            if method not in ("GET", "POST"):
                log.error(f"Invalid notify method (must be GET or POST): {method}")
                return
            self.method = method
            self.url = parts[1]
            headers = parts[2]
            if headers != "-" and "," in headers:
                for header in headers.split(","):
                    key, value = header.split("=")
                    self.headers[key] = value
            body = parts[3]
            if body != "-":
                self.body = body
            self.valid = True
            return
        else:
            log.error(f"Invalid notify target: {self.notify_str}")
            return

    def notify(self):
        if not self.valid:
            log.error("No valid notify target set")
            return False
        log.info(f"Notifying with {self.method} request to: {self.url}")
        headers = {"User-Agent": INTERNAL_USER_AGENT}
        for key, value in self.headers.items():
            if key not in headers:
                headers[key] = value
        if self.method == "GET":
            response = requests.get(self.url, headers=headers)
        elif self.method == "POST":
            response = requests.post(self.url, headers=headers, data=self.body)
        # check response status code is between 200 and 299
        if 200 <= response.status_code < 300:
            # print(response.text)
            return True
        else:
            log.error(
                f"Failed {self.method} to {self.url} - got response code: HTTP/{response.status_code}"
            )
            return False
