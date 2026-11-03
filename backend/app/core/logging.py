import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Send our `app.*` loggers (e.g. AI usage lines) to stderr alongside uvicorn's logs."""
    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(level)
    app_logger.propagate = False
