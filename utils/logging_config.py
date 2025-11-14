"""
Standardized Log4-style logging configuration for AI PDF Vector Stack
Format: YYYY-MM-DD HH:MM:SS.mmm | Program Name | Module | Severity | Message
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Log4Formatter(logging.Formatter):
    """Custom formatter for Log4-style logging with subsecond timestamps"""

    def format(self, record):
        # Get subsecond timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Extract program name from filename
        program_name = Path(record.pathname).stem

        # Get module name (logger name)
        module_name = record.name

        # Format: timestamp | program | module | severity | message
        formatted_message = f"{timestamp} | {program_name} | {module_name} | {record.levelname} | {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            formatted_message += f"\n{self.formatException(record.exc_info)}"

        return formatted_message


def setup_logging(
    program_name: Optional[str] = None,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> logging.Logger:
    """
    Setup standardized Log4-style logging for a Python script

    Args:
        program_name: Override program name (default: script filename)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path for file output
        console_output: Whether to output to console (default: True)

    Returns:
        Configured logger instance
    """
    # Get the calling script's name if not provided
    if program_name is None:
        frame = sys._getframe(1)
        program_name = Path(frame.f_code.co_filename).stem

    # Create logger
    logger = logging.getLogger(program_name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = Log4Formatter()

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler (if specified) or if LOG_DIR env var provided
    if log_file or os.getenv("LOG_DIR"):
        try:
            if not log_file:
                # Derive log file path from LOG_DIR env var
                base_dir = os.getenv("LOG_DIR", "./logs")
                Path(base_dir).mkdir(parents=True, exist_ok=True)
                log_file = str(Path(base_dir) / f"{program_name}.log")
            else:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to console-only if file logging fails
            logger.warning(f"File logging disabled due to error setting up log file '{log_file}': {e}")

    # Prevent propagation to avoid duplicate messages
    logger.propagate = False

    return logger


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for a specific module

    Args:
        module_name: Name of the module (default: calling function's module)

    Returns:
        Logger instance for the module
    """
    if module_name is None:
        frame = sys._getframe(1)
        module_name = frame.f_globals.get("__name__", "unknown")

    return logging.getLogger(module_name)


def configure_root_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
):
    """
    Configure the root logger with Log4-style formatting

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        console_output: Whether to output to console
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = Log4Formatter()

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file or os.getenv("LOG_DIR"):
        try:
            if not log_file:
                base_dir = os.getenv("LOG_DIR", "./logs")
                Path(base_dir).mkdir(parents=True, exist_ok=True)
                log_file = str(Path(base_dir) / "app.log")
            else:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"File logging disabled due to error: {e}")

    # Prevent duplicate messages
    root_logger.propagate = False


# Default logger setup for quick usage
def setup_default_logging():
    """Setup default logging configuration for scripts"""
    return setup_logging(log_level="INFO", console_output=True)
