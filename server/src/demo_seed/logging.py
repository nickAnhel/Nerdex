from __future__ import annotations

import logging


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [demo_seed] %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
