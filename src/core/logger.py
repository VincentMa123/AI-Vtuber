import logging
import os
import sys
import datetime
from types import SimpleNamespace

# Configuration defaults (simulating args)
# You can move these to config.py if you prefer global configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
DEFAULT_SILENT = False

# Mock args to match user's snippet structure, or just use these directly
args = SimpleNamespace(
    log_level=os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL),
    log_dir=os.getenv("LOG_DIR", DEFAULT_LOG_DIR),
    silent=False 
)

def get_current_time(include_ms=False, as_str=False):
    now = datetime.datetime.now()
    if not include_ms:
        now = now.replace(microsecond=0)
    if as_str:
        return now.strftime("%Y-%m-%d %H:%M:%S")
    return now

START_TIME = get_current_time(include_ms=False, as_str=False)

# Setup formatters and handlers
class CustomFormatter(logging.Formatter):
    # Using console color codes to style text
    reset = "\x1b[0m"
    base_time = "[%(asctime)s]" + reset
    base_level = "[%(levelname)-5.5s]" + reset
    base_func = "[%(filename)s::%(lineno)d %(funcName)s]:" + reset
    base_msg = "%(message)s" + reset

    # Styling: Time (Blue), Level (Background Colors), Function (Yellow), Message (Default)
    template_line = "\x1b[1m\x1b[1;34m" + base_time + " {}" + base_level + " \x1b[1m\x1b[1;33m" + base_func + " " + base_msg

    FORMATS = {
        logging.DEBUG: template_line.format("\x1b[1m\x1b[1;30m\x1b[47m"),      # White bg
        logging.INFO: template_line.format("\x1b[1m\x1b[1;30m\x1b[42m"),       # Green bg
        logging.WARNING: template_line.format("\x1b[1m\x1b[1;30m\x1b[43m"),    # Yellow bg
        logging.ERROR: template_line.format("\x1b[1m\x1b[1;30m\x1b[41m"),      # Red bg
        logging.CRITICAL: template_line.format("\x1b[1m\x1b[31m\x1b[45m")      # Purple bg
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)
    
def setup_logger():
    """Initialize the global logger with file and console handlers"""
    # Create logs directory if it doesn't exist
    if not os.path.exists(args.log_dir):
        os.makedirs(args.log_dir)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    # Remove existing handlers to avoid duplicates if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # File Handler
    log_filename = os.path.join(args.log_dir, "{}.log".format(get_current_time(include_ms=False).strftime("%Y-%m-%d")))
    file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)-5.5s] [%(filename)s::%(lineno)d %(funcName)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler
    if not args.silent:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)
    
    logging.info(f"Logger initialized. Log file: {log_filename}")
