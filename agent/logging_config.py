"""Logging setup: short lines to the console, full log (prompts and answers) to a file."""
from __future__ import annotations

import logging

from agent.settings import LoggingSettings

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(cfg: LoggingSettings) -> None:
    """Call once at program start. Safe to call again (e.g. on Streamlit reruns)."""
    root = logging.getLogger()
    if getattr(root, "_agent_configured", False):
        return
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(cfg.console_level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    root.addHandler(console)

    cfg.dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(cfg.dir / cfg.file_name, encoding="utf-8")
    file_handler.setLevel(cfg.file_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(file_handler)

    for name in cfg.quiet_libraries:
        logging.getLogger(name).setLevel(logging.WARNING)
    root._agent_configured = True
