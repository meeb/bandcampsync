VERSION = "0.8.0"
INTERNAL_USER_AGENT = f"bandcampsync/{VERSION}"
# curl_cffi's "chrome" alias is currently rejected by Bandcamp's Fastly client
# challenge, which returns a small "Client Challenge" page and no HomepageApp
# markup. These fingerprints still receive the real site and are tried in order.
BROWSER_PROFILES = (
    "chrome146",
    "chrome150",
    "firefox155",
    "safari260",
)
