import structlog
import logging
from voucherbot.config.settings import settings

def setup_logging() -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    
    logging.basicConfig(
        format="%(message)s",
        stream=None,
        level=log_level,
    )
