import logging
from abc import ABC

from utils import logging_config  # noqa: F401


class BaseProcessor(ABC):
    """Classe de base pour tous les processeurs de fichiers"""

    def __init__(self):
        """Initialiser le processeur de base avec le logger global"""

        self.logger = logging.getLogger(__name__)

    def log_info(self, message: str):
        self.logger.info(message)

    def log_warning(self, message: str):
        self.logger.warning(message)

    def log_error(self, message: str):
        self.logger.error(message)

    def log_success(self, message: str):
        self.logger.info(message)

    def log_debug(self, message: str):
        self.logger.debug(message)
