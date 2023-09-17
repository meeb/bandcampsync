import json
from time import time
from http.cookies import BaseCookie
from html import unescape as html_unescape
from urllib.parse import urlsplit, urlunsplit
from bs4 import BeautifulSoup
import requests
from .config import USER_AGENT
from .logger import get_logger


log = get_logger('bandcamp')


class BandcampError(ValueError):
    pass


class Bandcamp:

    BASE_PROTO = 'https'
    BASE_DOMAIN = 'bandcamp.com'
    URLS = {
        'index': '/',
        'collection_items': '/api/fancollection/1/collection_items',
    }

    def __init__(self, cookies=''):
        self.is_authenticated = False
        self.user_id = 0
        self.user_name = ''
        self.user_url = ''
        self.user_verified = False
        self.user_private = False
        self.cookies = BaseCookie()
        self.purchases = []
        try:
            self.cookies.load(cookies)
        except Exception as e:
            raise BandcampError(f'Failed to parse cookies string: {e}') from e
        session = self.cookies.get('session')
        if not session:
            raise BandcampError(f'Cookie data does not contain a session value, make sure your '
                                f'cookies.txt file is valid and you copied it from an '
                                f'authenticated browser')
        session_snip = session.value[:20]
        log.info(f'Located Bandcamp session in cookies: {session_snip}...')

    @property
    def cookies_str(self):
        return self.cookies.output(header='').strip().replace('\r\n', ';')

    def refresh_cookes(self, file_path):
        log.info(f'Refreshing cookies: {file_path}')
        with open(file_path, 'wt') as f:
            f.write(self.cookies_str)

    def _construct_url(self, url_name):
        if url_name not in self.URLS:
            raise BandcampError(f'URL name is unknown: {url_name}')
        return urlunsplit((self.BASE_PROTO, self.BASE_DOMAIN, self.URLS[url_name], '', ''))

    def _plain_cookies(self):
        cookies = {}
        for (cookie_name, cookie_value) in self.cookies.items():
            cookies[cookie_value.key] = cookie_value.value
        return cookies

    def _request(self, method, url, data={}, json_data={}, is_json=False):
        headers = {'User-Agent': USER_AGENT}
        try:
            log.debug(f'Making {method} request to {url}')
            response = requests.request(
                method,
                url,
                headers=headers,
                cookies=self._plain_cookies(),
                data=data,
                json=json_data
            )
        except Exception as e:
            raise BandcampError(f'Failed to make HTTP request to {url}: {e}') from e
        if response.status_code != 200:
            raise BandcampError(f'Failed to make HTTP request to {url}: '
                                f'unknown status code response: {response.status_code}')
        try:
            # If there are updated cookies returned from in the response header update our
            # local cookie jar
            set_cookie = response.headers['set-cookie']
            self.cookies.load(set_cookie)
        except Exception:
            pass
        if is_json:
            return json.loads(response.text)
        else:
            return BeautifulSoup(response.text, 'html.parser')

    def _extract_pagedata(self, soup):
        pagedata_tag = soup.find('div', id='pagedata')
        if not pagedata_tag:
            raise BandcampError(f'Failed to locate <div id="pagedata"> in index HTML, this may '
                                f'be an authentication issue or it may be that bandcamp.com has '
                                f'updated their website and this tool needs to be updated.')
        encoded_pagedata = pagedata_tag.attrs.get('data-blob')
        if not encoded_pagedata:
            raise BandcampError(f'Failed to extract page data, check your cookies are from an ',
                                f'authenticated session')
        pagedata_str = html_unescape(encoded_pagedata)
        try:
            return json.loads(pagedata_str)
        except Exception as e:
            raise BandcampError(f'Failed to parse pagedata as JSON: {e}') from e

    def verify_authentication(self):
        """
            Loads the initial account and session data from a request to the index page
            of bandcamp.com. When properly authenticated an HTML data attribute is present
            that contains account information in an encoded form.
        """
        url = self._construct_url('index')
        soup = self._request('get', url)
        pagedata = self._extract_pagedata(soup)
        try:
            identities = pagedata['identities']
        except KeyError as e:
            raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                f'"identities" key') from e
        try:
            fan = identities['fan']
        except KeyError as e:
            raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                f'"identities.fan" key') from e
        try:
            self.user_id = fan['id']
            self.user_name = fan['name']
            self.user_url = fan['url']
            self.user_verified = fan['verified']
            self.user_private = fan['private']
        except KeyError as e:
            raise BandcampError(f'Failed to parse pagedata JSON, "identities.fan" seems '
                                f'invalid: {fan}') from e
        self.is_authenticated = self.user_id > 0
        log.info(f'Loaded page data, session is authenticated for user '
                 f'"{self.user_name}" (id:{self.user_id}, url:{self.user_url})')
        return True

    def load_purchases(self):
        """
            Loads all purchases on the authenticated account and returns a list of
            purchase data. Each purchase is a dict of data.
        """
        if not self.is_authenticated:
            raise BandcampError(f'Authentication not verified, call load_pagedata() first')
        log.info(f'Loading purchases for: {self.user_name} (id:{self.user_id})')
        self.purchases = []
        now = int(time())
        page_ts = 0
        token = f'{now}:{page_ts}:a::'
        per_page = 100
        while(True):
            log.info(f'Requesting {per_page} purchases using token {token}')
            data = {
                'fan_id': self.user_id,
                'count': per_page,
                'older_than_token': token
            }
            url = self._construct_url('collection_items')
            data = self._request('POST', url, json_data=data, is_json=True)
            try:
                items = data['items']
            except KeyError as e:
                raise BandcampError(f'Failed to extract items from collection results page')
            if not items:
                log.info(f'Reached end of items')
                break
            try:
                redownload_urls = data['redownload_urls']
            except KeyError as e:
                raise BandcampError(f'Failed to extract redownload_urls from collection results page')
            for item in items:
                item_id = item['item_id']
                band_name = item['band_name']
                title = item['item_title']
                token = item['token']
                log.info(f'Found item: {band_name} / {title} (id:{item_id})')
                download_url_type = item['sale_item_type']
                download_url_id = item['sale_item_id']
                download_url_key = f'{download_url_type}{download_url_id}'
                try:
                    download_url = redownload_urls[download_url_key]
                except KeyError:
                    log.error(f'Failed to locate download URL for {band_name} / {title} '
                              f'(key:{download_url_key}), skipping item...')
                    continue
                item['download_url'] = download_url
                self.purchases.append(item)
        log.info(f'Loaded {len(self.purchases)} purchases')
        #print(json.dumps(self.purchases[0], indent=4, sort_keys=True))
        return True

    def load_download_url(self, purchase, encoding='flac'):
        """
            Fetches the download URL for a purchase in the requested format.
            Defaults to FLAC.
        """
        download_url = purchase['download_url']
        item_id = purchase['item_id']
        item_type = purchase['item_type']
        if item_type not in ('album', 'track'):
            band_name = item['band_name']
            title = item['item_title']
            log.error(f'Item {item_id} ({band_name} / {title}) has an unknown item type: {item_type}, skipping')
            return False
        # get the pagedata
        soup = self._request('get', download_url)
        pagedata = self._extract_pagedata(soup)
        try:
            digital_items = pagedata['digital_items']
        except KeyError as e:
            raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                f'"digital_items" key') from e
        for digital_item in digital_items:
            try:
                digital_item_id = digital_item['item_id']
            except KeyError as e:
                raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                    f'"digital_items[].art_id" key') from e
            if digital_item_id == item_id:
                try:
                    downloads = digital_item['downloads']
                except KeyError as e:
                    raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                        f'"digital_items.downloads" key') from e
                try:
                    download_format = downloads[encoding]
                except KeyError as e:
                    encodings = download_format.keys()
                    raise BandcampError(f'Download formats does not contain requested encoding: {encoding} '
                                        f'(available encodings: {encodings})') from e
                try:
                    return download_format['url']
                except KeyError as e:
                    raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                        f'"digital_items.downloads.[encoding].url" key') from e
        return False
