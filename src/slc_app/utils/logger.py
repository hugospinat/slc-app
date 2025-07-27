import logging
import sys

LOGGER_NAME = "slc_app"


logger = logging.getLogger(LOGGER_NAME)
if not logger.hasHandlers():
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    # File handler
    file_handler = logging.FileHandler("slc_app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

# Pour usage direct :
# from slc_app.utils.logger import logger
# logger.info("Message")
