from cmath import log
import logging

import os
import sys
from scanner_constants import LOGS_PATH, USING_AWS_LAMBDA

def getScannerLogger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logfmt = "%(asctime)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d [%(levelname)s]: %(message)s"
    log_formatter = logging.Formatter(logfmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(log_formatter)
    ch.setLevel(logging.DEBUG if USING_AWS_LAMBDA else logging.INFO)
    logger.addHandler(ch)

    if not USING_AWS_LAMBDA:
        os.makedirs(os.path.dirname(LOGS_PATH), exist_ok=True)
        fh = logging.FileHandler(LOGS_PATH, "w")
        fh.setFormatter(log_formatter)
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
    else:
        logger.propagate = False # Prevent log duplication in AWS lambda

    return logger