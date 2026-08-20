"""Configures a named stdlib logger with a consistent console format.

Lives in domain, not interface, despite being about log output: nearly every
domain module (bandcamp, download, ignores, media, notify) calls this
directly, and domain must not depend on interface.
"""

import logging


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(level)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(name)s [%(levelname)s] %(message)s")
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log
