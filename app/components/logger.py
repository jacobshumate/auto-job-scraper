import logging
import sys
from datetime import datetime, timedelta, timezone

class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Determine if daylight saving time is in effect
        now = datetime.now()
        is_dst = now.dst() != timedelta(0)

        offset_hours = -6 if is_dst else -7
        # Get the current local time from the timestamp
        local_time = datetime.fromtimestamp(record.created, timezone(timedelta(hours=offset_hours)))
        if datefmt:
            # Format to include only milliseconds
            return local_time.strftime(datefmt)[:-3]
        else:
            return local_time.strftime('%m-%d %H:%M:%S,%f')

class Logger:
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }  # relationship mapping

    def __init__(self, modulename, level='info', fmt='%(asctime)s [%(levelname)s] %(message)s'):
        self.logger = logging.getLogger(modulename)
        if not self.logger.handlers:
            self.logger.setLevel(self.level_relations.get(level))

            handler = logging.StreamHandler(sys.stdout)
            formatter = LocalTimeFormatter(fmt, datefmt='%m-%d %H:%M:%S,%f')
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

    def set_level(self, level):
        """Dynamically set the log level."""
        self.logger.setLevel(self.level_relations.get(level))

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)
