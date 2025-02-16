import requests
from .config import INTERNAL_USER_AGENT
from .logger import get_logger


log = get_logger('notify')


class NotifyURL:

    def __init__(self, url):
        self.url = url

    def notify(self):
        log.info(f'Notifying with GET request to: {self.url}')
        headers = {'User-Agent': INTERNAL_USER_AGENT}
        response = requests.get(self.url, headers=headers)
        # check response status code is between 200 and 299
        if 200 <= response.status_code < 300:
            return True
        else:
            log.error(f'Failed to notify {self.url} - got response code: HTTP/{response.status_code}')
            return False
