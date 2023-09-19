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

    def _get_redirect_url(self, url):
        """
            Requests (HTTP GET) a URL assuming it will return a redirect (301 or
            303) and return the URL you are being redirected to.
        """
        headers = {'User-Agent': USER_AGENT}
        try:
            log.debug(f'Making GET (redirect check) request to {url}')
            response = requests.get(
                url,
                headers=headers,
                cookies=self._plain_cookies(),
                allow_redirects=False
            )
        except Exception as e:
            raise BandcampError(f'Failed to make HTTP request to {url}: {e}') from e
        if response.status_code in (301, 303):
            try:
                return response.headers['Location']
            except KeyError as e:
                raise BandcampError(f'Redirect URL {url} returned a 301 or 303 but no Location header')
        else:
            # Not a redirect
            return False

    def _extract_pagedata_from_soup(self, soup):
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

    def _extract_pagedata_from_html(self, html):
        """
            Wrapper for _extract_pagedata_from_soup() that can accept HTML rather than a bs4 soup.
        """
        soup = BeautifulSoup(html, 'html.parser')
        return self._extract_pagedata_from_soup(soup)

    def verify_authentication(self):
        """
            Loads the initial account and session data from a request to the index page
            of bandcamp.com. When properly authenticated an HTML data attribute is present
            that contains account information in an encoded form.
        """
        url = self._construct_url('index')
        soup = self._request('get', url)
        pagedata = self._extract_pagedata_from_soup(soup)
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
                 f'"{self.user_name}" (user id:{self.user_id}, url:{self.user_url})')
        return True

    def load_purchases(self):
        """
            Loads all purchases on the authenticated account and returns a list of
            purchase data. Each purchase is a dict of data.
        """
        if not self.is_authenticated:
            raise BandcampError(f'Authentication not verified, call load_pagedata() first')
        log.info(f'Loading purchases for: {self.user_name} (user id:{self.user_id})')
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
            for item_data in items:
                sale_item_type = item_data['sale_item_type']
                sale_item_id = item_data['sale_item_id']
                download_url_key = f'{sale_item_type}{sale_item_id}'
                try:
                    download_url = redownload_urls[download_url_key]
                except KeyError:
                    log.error(f'Failed to locate download URL for {item.band_name} / {item.title} '
                              f'(key:{download_url_key}), skipping item...')
                    continue
                item_data['download_url'] = download_url
                item = BandcampItem(item_data)
                token = item.token
                log.info(f'Found item: {item.band_name} / {item.item_title} (id:{item.item_id})')
                self.purchases.append(item)
        log.info(f'Loaded {len(self.purchases)} purchases')
        return True
    
    def get_download_file_url(self, item, encoding='flac'):
        soup = self._request('get', item.download_url)
        pagedata = self._extract_pagedata_from_soup(soup)
        download_url = None
        if not pagedata:
            raise ValueError(f'Either "url" or "pagedata" must be supplied')
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
            if digital_item_id == item.item_id:
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
                    download_url = download_format['url']
                except KeyError as e:
                    raise BandcampError(f'Failed to parse pagedata JSON, does not contain an '
                                        f'"digital_items.downloads.[encoding].url" key') from e
                return download_url
        return False


class BandcampItem:

    def __init__(self, data):
        self._data = data

    def __repr__(self):
        return json.dumps(self._data, indent=4, sort_keys=True)

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError as e:
            raise KeyError(f'BandcampItem value "{key}" does not exist') from e
