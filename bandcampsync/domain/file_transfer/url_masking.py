def mask_signed_url(url: str) -> str:
    if "&sig=" not in url:
        return url
    url_parts = url.split("&")
    for i, url_part in enumerate(url_parts):
        if url_part[:4] == "sig=":
            url_parts[i] = "sig=[masked]"
        elif url_part[:6] == "token=":
            url_parts[i] = "token=[masked]"
    return "&".join(url_parts)
