import logging
import sys


class Logger:
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }  # relationship mapping

    def __init__(self, modulename, level='info', fmt='%(asctime)s [%(levelname)s] %(message)s'):
        logging.basicConfig(
            level=self.level_relations.get(level),
            format=fmt,
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(modulename)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)