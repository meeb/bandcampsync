import hashlib
import os
import re
from unicodedata import category


# Filesystems limit names to either 255 bytes, 255 UTF-16 units or sometimes fewer, such
# as 143 bytes on eCryptfs. A name that fits in bytes always fits in UTF-16 units too.
SHORTENED_NAME_BYTES = (255, 143)
# Combining marks along with control, format and surrogate characters. These are the
# bulk of very long "zalgo" style names and can't be used on every filesystem.
REMOVED_CATEGORIES = ("Mn", "Me", "Cc", "Cf", "Cs")
MAX_EXTENSION_BYTES = 16


def is_usable_name(directory, name):
    """
    Asks the filesystem if a name can be used in a directory without creating anything.
    The directory must exist as nothing else is checked if it's missing.
    """
    # Windows can report a name that's too long as simply not being found
    if os.name == "nt" and len(name.encode("utf-16-le", "surrogatepass")) > 510:
        return False
    try:
        os.lstat(os.path.join(directory, name))
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return True


def fit_name(directory, name, keep_extension=False):
    """
    Returns the name unchanged if the filesystem can use it, so existing directories
    and files always keep their names. Otherwise returns a shortened name which is the
    same every time and has a hash of the full name to keep it unique.
    """
    if is_usable_name(directory, name):
        return name
    digest = hashlib.sha1(name.encode("utf-8", "surrogatepass")).hexdigest()[:8]
    kept = "".join(c for c in name if category(c) not in REMOVED_CATEGORIES)
    kept = re.sub(r"\s+", " ", kept).strip(" .")
    extension = ""
    if keep_extension:
        stem, extension = os.path.splitext(kept)
        if len(extension.encode()) <= MAX_EXTENSION_BYTES:
            kept = stem
        else:
            extension = ""
    marker = f"~{digest}{extension}"
    shortened = marker
    for limit in SHORTENED_NAME_BYTES:
        room = limit - len(marker.encode())
        cut = kept.encode()[:room].decode(errors="ignore").rstrip(" .")
        shortened = f"{cut}{marker}"
        if is_usable_name(directory, shortened):
            break
    return shortened
