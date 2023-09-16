import sys
import logging


def get_logger(name, level=logging.INFO):
    log = logging.getLogger(name)
    log.setLevel(level)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    fmt = logging.Formatter('%(asctime)s %(name)s [%(levelname)s] %(message)s')
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log
