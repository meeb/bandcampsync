VERSION = "0.8.0"
INTERNAL_USER_AGENT = f"bandcampsync/{VERSION}"
# Bandcamp's Fastly client challenge rejects some curl_cffi fingerprints, including
# the "chrome" alias and "chrome150", returning a small "Client Challenge" page with
# no HomepageApp markup. These fingerprints still receive the real site and are tried
# in order, waiting BROWSER_PROFILE_WAIT seconds between each one.
BROWSER_PROFILES = (
    "chrome146",
    "firefox155",
    "safari260",
)
BROWSER_PROFILE_WAIT = 1
