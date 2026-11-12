"""Timing helpers with no URL parameters or exception details in own logs."""

import logging
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

logger = logging.getLogger("Core_Update.timings")


@contextmanager
def measure(label):
    perf_counter()
    try:
        yield
    finally:
        # logger.info(
        #     "[TIME] %s : %.3f s %s",
        #     label,
        #     perf_counter() - start,
        #     "OK" if ok else "ERREUR/ANNULATION",
        # )
        pass


def install():
    if logger.handlers:
        return
    handler = logging.FileHandler(
        Path(__file__).with_name("timings.log"), encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
