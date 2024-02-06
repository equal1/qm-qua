import logging
from logging import config

from qm.user_config import UserConfig


def config_loggers(user_config: UserConfig) -> None:
    config.dictConfig(user_config.logging_config_dict)


def set_logging_level(level: int) -> None:
    """Sets the logging level of the qm-qua module ("qm")
    See `Messages control <https://qm-docs.qualang.io/guides/error#messages-control>`__ for more information.

    Args:
        level: A string of either: 'DEBUG', 'INFO', 'WARNING', or
            'ERROR'. Can also accept standard python logging levels.
    """
    package_logger = logging.getLogger("qm")
    try:
        package_logger.setLevel(level)
    except (ValueError, TypeError):
        package_logger.warning(f"Failed to set log level. level '{level}' is not recognized")
