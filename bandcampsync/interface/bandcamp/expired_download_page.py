"""Detects Bandcamp's "this download link needs to be re-confirmed by email"
page, which their CDN serves as a normal HTML response rather than an error.
"""

from bs4 import BeautifulSoup


def is_expired_download_page(html: str) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    reauth_error = soup.select_one("div.email-reauth-error")
    if not reauth_error:
        return False
    style = str(reauth_error.get("style")) or ""
    style = style.replace(" ", "").lower()
    return "display:none" not in style
