import re


def parse_js_stat_url(body: str, download_url: str) -> str:
    """Checks the "stat" download URL body, which is in JavaScript, for
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
            return str(v)
    # Fallback to the original download URL
    return download_url
