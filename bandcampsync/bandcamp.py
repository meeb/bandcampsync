import json
import re
from time import time
from http.cookies import SimpleCookie
from html import unescape as html_unescape
from urllib.parse import urlsplit, urlunsplit
from bs4 import BeautifulSoup
from curl_cffi import requests
from .download import mask_sig
from .logger import get_logger


log = get_logger("bandcamp")


class BandcampError(ValueError):
    pass


class BandcampDownloadUnavailable(BandcampError):
    pass


class Bandcamp:
    BASE_PROTO = "https"
    BASE_DOMAIN = "bandcamp.com"
    URLS = {
        "index": "/",
        "collection_items": "/api/fancollection/1/collection_items",
    }

    def __init__(self, cookies=""):
        self.is_authenticated = False
        self.user_id = 0
        self.user_verified = False
        self.cookies = None
        self.purchases = []
        self.load_cookies(cookies)
        identity = self.cookies.get("identity")
        if not identity:
            raise BandcampError(
                "Cookie data does not contain an identity value, make sure your "
                "cookies.txt file is valid and you copied it from an "
                "authenticated browser"
            )
        identity_snip = identity.value[:20]
        log.info(f"Located Bandcamp identity in cookies: {identity_snip}...")
        # Create a requests session and map our SimpleCookie to it
        self.session = requests.Session(impersonate="chrome")
        for cookie_name, morsel in self.cookies.items():
            self.session.cookies.set(cookie_name, morsel.value)

    def load_cookies(self, cookies_str):
        self.cookies = SimpleCookie()
        try:
            self.cookies.load(cookies_str)
        except Exception as e:
            raise BandcampError(f"Failed to parse cookies string: {e}") from e
        if len(self.cookies) == 0:
            # Failed to load any cookies, attempt to parse the cookies string as a Netscape cookies export
            lines = cookies_str.strip().split("\n")
            for line in lines:
                if line.startswith("#"):
                    continue
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) == 7:
                    domain, tailmatch, path, secure, expires, name, value = parts
                    cookie_string = f"{name.strip()}={value.strip()}; Domain={domain.strip()}; Path={path.strip()}"
                    if secure == "TRUE":
                        cookie_string += "; Secure"
                    self.cookies.load(cookie_string)
        return True

    @property
    def cookies_str(self):
        return self.cookies.output(header="").strip().replace("\r\n", ";")

    def refresh_cookes(self, file_path):
        log.info(f"Refreshing cookies: {file_path}")
        with open(file_path, "wt") as f:
            f.write(self.cookies_str)

    def _construct_url(self, url_name):
        if url_name not in self.URLS:
            raise BandcampError(f"URL name is unknown: {url_name}")
        return urlunsplit(
            (self.BASE_PROTO, self.BASE_DOMAIN, self.URLS[url_name], "", "")
        )

    def _plain_cookies(self):
        cookies = {}
        for cookie_name, cookie_value in self.cookies.items():
            cookies[cookie_value.key] = cookie_value.value
        return cookies

    def _request(
        self, method, url, data=None, json_data=None, is_json=False, as_raw=False
    ):
        try:
            # The debug logs do not mask the URL which may be a security issue if you run
            # with level=logging.DEBUG
            log.debug(f"Making {method} request to {url}")
            response = self.session.request(
                method,
                url,
                cookies=self._plain_cookies(),
                data=data,
                json=json_data,
            )
        except Exception as e:
            raise BandcampError(
                f"Failed to make HTTP request to {mask_sig(url)}: {e}"
            ) from e
        if response.status_code != 200:
            raise BandcampError(
                f"Failed to make HTTP request to {mask_sig(url)}: "
                f"unknown status code response: {response.status_code}"
            )
        if as_raw:
            return response.text
        elif is_json:
            return json.loads(response.text)
        else:
            return BeautifulSoup(response.text, "html.parser")

    def _extract_pagedata_from_soup(self, soup, id_name="pagedata"):
        pagedata_tag = soup.find("div", id=id_name)
        if not pagedata_tag:
            raise BandcampError(
                'Failed to locate <div id="HomepageApp"> in index HTML, this may '
                "be an authentication issue or it may be that bandcamp.com has "
                "updated their website and this tool needs to be updated."
            )
        encoded_pagedata = pagedata_tag.attrs.get("data-blob")
        if not encoded_pagedata:
            raise BandcampError(
                "Failed to extract page data, check your cookies are from an ",
                "authenticated session",
            )
        pagedata_str = html_unescape(encoded_pagedata)
        try:
            return json.loads(pagedata_str)
        except Exception as e:
            raise BandcampError(f"Failed to parse pagedata as JSON: {e}") from e

    def _extract_pagedata_from_html(self, html):
        """
        Wrapper for _extract_pagedata_from_soup() that can accept HTML rather than a bs4 soup.
        """
        soup = BeautifulSoup(html, "html.parser")
        return self._extract_pagedata_from_soup(soup)

    def _get_js_stat_url(self, body, download_url):
        """
        Checks the "stat" download URL body, which is in JavaScript, for
        either the OK response or a new updated download URL.
        """
        body = body.strip()
        if body == "var _statDL_result = { result: 'ok'};":
            # Download is OK, original download URL will work
            return download_url
        # Attempt to find the updated download_url in the JavaScript with a hacky regex
        pattern = re.compile('"([^"]+)":"([^"]+)"')
        for k, v in pattern.findall(body):
            if k == "download_url":
                return v
        # Fallback to the original download URL
        return download_url

    def verify_authentication(self):
        """
        Loads the initial account and session data from a request to the index page
        of bandcamp.com. When properly authenticated an HTML data attribute is present
        that contains account information in an encoded form.
        """
        url = self._construct_url("index")
        soup = self._request("get", url)
        pagedata = self._extract_pagedata_from_soup(soup, id_name="HomepageApp")
        try:
            pagecontext = pagedata["pageContext"]
        except KeyError as e:
            raise BandcampError(
                'Failed to parse pagedata JSON, does not contain an "pageContext" key'
            ) from e
        try:
            identity = pagecontext["identity"]
        except KeyError as e:
            raise BandcampError(
                'Failed to parse pagecontext JSON, does not contain an "identity" key'
            ) from e
        if not isinstance(identity, dict):
            raise BandcampError(
                'Failed to parse pagedata JSON, "identity" is not '
                "a dictionary. Check your cookies.txt file is valid "
                "and up to date"
            )
        try:
            self.user_id = identity["fanId"]
            self.user_verified = identity["isFanVerified"]
        except (KeyError, TypeError) as e:
            raise BandcampError(
                f'Failed to parse pagedata JSON, "identity.fan" seems invalid: {identity}'
            ) from e
        self.is_authenticated = self.user_id > 0
        log.info(
            f"Loaded page data, session is authenticated for user id: {self.user_id})"
        )
        return True

    def _resolve_download_url(self, item, redownload_urls):
        sale_item_type = item.sale_item_type
        sale_item_id = item.sale_item_id
        if sale_item_type is None or sale_item_id is None:
            log.error(
                f"Failed to locate sale item metadata for {item.band_name} / {item.item_title}, skipping item..."
            )
            return None
        download_url_key = f"{sale_item_type}{sale_item_id}"
        download_url = redownload_urls.get(download_url_key)
        if not download_url:
            if item.is_physical_purchase():
                log.info(
                    f"No download available for physical purchase {item.band_name} / {item.item_title} (key:{download_url_key}), skipping"
                )
            else:
                log.warning(
                    f"No download available for {item.band_name} / {item.item_title} (key:{download_url_key}), skipping item..."
                )
            return None
        return download_url

    def _deduplicate_purchases(self, grouped_items):
        for item_key, items in grouped_items.items():
            count = len(items)
            if count == 1:
                continue
            duplicate = items[0]
            item_ids = ", ".join(str(item.item_id) for item in items)
            log.info(
                f'Found {count} collection entries with the same name: "{duplicate.band_name} / {duplicate.item_title}" (ids: {item_ids})'
            )
            duplicate_details = []
            for item in items:
                log.debug(f"Duplicate entry: url={item.download_url}")
                duplicate_details.append(
                    f"id={item.item_id} item_type={getattr(item, 'item_type', '')} "
                    f"sale_item_type={item.sale_item_type} sale_item_id={item.sale_item_id}"
                )
                # Use the item ID as a suffix to ensure duplicates are downloaded to distinct folders.
                item.folder_suffix = f" [{item.item_id}]"
            log.debug(
                f"Duplicate name details: {duplicate.band_name} / {duplicate.item_title}: {', '.join(duplicate_details)}"
            )

    def load_purchases(self):
        """
        Loads all purchases on the authenticated account and returns a list of
        purchase data. Each purchase is a dict of data.
        """
        if not self.is_authenticated:
            raise BandcampError(
                "Authentication not verified, call load_pagedata() first"
            )
        log.info(f"Loading purchases for user id: {self.user_id}")
        self.purchases = []
        now = int(time())
        page_ts = 0
        token = f"{now}:{page_ts}:a::"
        per_page = 100
        items_by_title_key = {}
        while True:
            log.info(f"Requesting {per_page} purchases using token {token}")
            data = {
                "fan_id": self.user_id,
                "count": per_page,
                "older_than_token": token,
            }
            url = self._construct_url("collection_items")
            data = self._request("POST", url, json_data=data, is_json=True)
            try:
                items = data["items"]
            except KeyError:
                raise BandcampError(
                    "Failed to extract items from collection results page"
                )
            if not items:
                log.info("Reached end of items")
                break
            try:
                redownload_urls = data["redownload_urls"]
            except KeyError:
                raise BandcampError(
                    "Failed to extract redownload_urls from collection results page"
                )
            for item_data in items:
                item = BandcampItem(item_data)
                item_token = item.token
                if item_token is not None:
                    token = item_token
                if not item.band_name:
                    log.error(
                        "Failed to locate band name in item metadata, skipping item..."
                    )
                    continue
                if not item.item_title:
                    log.error(
                        f'Failed to locate title in item metadata (possibly a subscription?) for "{item.band_name}", skipping item...'
                    )
                    continue
                if item.item_id is None:
                    log.error(
                        f"Failed to locate download URL for {band_name} / {title} "
                        f'Failed to locate item id for "{item.band_name} / {item.item_title}", skipping item...'
                    )
                    continue
                download_url = self._resolve_download_url(item, redownload_urls)
                if not download_url:
                    continue
                item.download_url = download_url
                item_key = (item.band_name, item.item_title)
                items_by_title_key.setdefault(item_key, []).append(item)
                log.info(f"Found item: {item.band_name} / {item.item_title} (id:{item.item_id})")
                self.purchases.append(item)

        # De-duplicate multiple purchases sharing the same artist and title.
        self._deduplicate_purchases(items_by_title_key)
        log.info(f"Loaded {len(self.purchases)} purchases")
        return True

    def get_download_file_url(self, item, encoding="flac"):
        soup = self._request("get", item.download_url)
        pagedata = self._extract_pagedata_from_soup(soup)
        download_url = None
        if not pagedata:
            raise BandcampError("No download information found for item")
        try:
            digital_items = pagedata["digital_items"]
        except KeyError as e:
            raise BandcampError(
                'Failed to parse pagedata JSON, does not contain an "digital_items" key'
            ) from e
        for digital_item in digital_items:
            try:
                digital_item_id = digital_item["item_id"]
            except KeyError as e:
                raise BandcampError(
                    "Failed to parse pagedata JSON, does not contain an "
                    '"digital_items[].art_id" key'
                ) from e
            if digital_item_id == item.item_id:
                try:
                    downloads = digital_item["downloads"]
                except KeyError as e:
                    raise BandcampError(
                        "Failed to parse pagedata JSON, does not contain an "
                        '"digital_items.downloads" key'
                    ) from e
                try:
                    download_format = downloads[encoding]
                except KeyError as e:
                    encodings = downloads.keys()
                    raise BandcampError(
                        f"Download formats does not contain requested encoding: {encoding} "
                        f"(available encodings: {encodings})"
                    ) from e
                try:
                    download_url = download_format["url"]
                except KeyError as e:
                    raise BandcampError(
                        "Failed to parse pagedata JSON, does not contain an "
                        '"digital_items.downloads.[encoding].url" key'
                    ) from e
                return download_url
        raise BandcampDownloadUnavailable("No download available for item")

    def check_download_stat(self, item, file_download_url):
        """
        Constructs the download "stat" URL and verifies the state of the download.
        If the state is OK, return the existing URL (download is OK) otherwise wait
        for the stat to complete and return the new download URL.
        """
        download_url_parts = urlsplit(file_download_url)
        path = download_url_parts.path
        path_parts = path.split("/")
        if path_parts[1] == "download":
            path_parts[1] = "statdownload"
        stat_url = urlunsplit(
            (
                download_url_parts.scheme,
                download_url_parts.netloc,
                "/".join(path_parts),
                download_url_parts.query,
                "",
            )
        )
        body = self._request("get", stat_url, as_raw=True)
        return self._get_js_stat_url(body, file_download_url)


class BandcampItem:
    def __init__(self, data):
        self._data = data
        self._data.setdefault("folder_suffix", "")

    @property
    def band_name(self):
        return self._data.get("band_name")

    @property
    def item_title(self):
        return self._data.get("item_title")

    @property
    def item_id(self):
        return self._data.get("item_id")

    @property
    def sale_item_type(self):
        return self._data.get("sale_item_type")

    @property
    def sale_item_id(self):
        return self._data.get("sale_item_id")

    @property
    def token(self):
        return self._data.get("token")

    @property
    def download_url(self):
        return self._data.get("download_url")

    @download_url.setter
    def download_url(self, value):
        self._data["download_url"] = value

    @property
    def folder_suffix(self):
        return self._data["folder_suffix"]

    @folder_suffix.setter
    def folder_suffix(self, value):
        self._data["folder_suffix"] = value

    def is_physical_purchase(self):
        # Note that this only tells us that this is a physical purchase, not whether or not there's also a digital download.
        item_type = self._data.get("item_type")
        if item_type:
            return item_type == "package"
        return self._data.get("sale_item_type") == "p"

    def __repr__(self):
        return json.dumps(self._data, indent=4, sort_keys=True)

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError as e:
            raise KeyError(f'BandcampItem value "{key}" does not exist') from e
