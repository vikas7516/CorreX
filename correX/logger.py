"""Centralized logging configuration for CorreX application.

Provides a unified logging interface to replace scattered print() statements
throughout the codebase with proper structured logging.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class CorreXLogger:
    """Centralized logger for CorreX application."""
    
    _loggers = {}
    _default_level = logging.INFO
    _log_file = None
    _initialized = False
    
    @classmethod
    def setup(
        cls,
        level: int = logging.INFO,
        log_file: Optional[Path] = None,
        console: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 3
    ) -> None:
        """Configure global logging settings.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_file: Optional path to log file (enables file logging)
            console: Whether to output to console (default: True)
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup log files to keep
        """
        cls._default_level = level
        cls._log_file = log_file
        cls._initialized = True
        
        # Configure root logger
        root_logger = logging.getLogger("CorreX")
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # File handler (rotating)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get or create a logger for a specific module.
        
        Args:
            name: Logger name (typically __name__ of the module)
        
        Returns:
            Configured Logger instance
        """
        if not cls._initialized:
            cls.setup()
        
        if name not in cls._loggers:
            logger = logging.getLogger(f"CorreX.{name}")
            logger.setLevel(cls._default_level)
            cls._loggers[name] = logger
        
        return cls._loggers[name]
    
    @classmethod
    def set_level(cls, level: int) -> None:
        """Change logging level for all loggers.
        
        Args:
            level: New logging level (DEBUG, INFO, WARNING, ERROR)
        """
        cls._default_level = level
        root_logger = logging.getLogger("CorreX")
        root_logger.setLevel(level)
        
        for logger in cls._loggers.values():
            logger.setLevel(level)


# Convenience function for quick logger access
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.
    
    Usage:
        from correX.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
        logger.error("Error occurred", exc_info=True)
    
    Args:
        name: Module name (use __name__)
    
    Returns:
        Configured Logger instance
    """
    return CorreXLogger.get_logger(name)


# Legacy compatibility - functions that mimic print() statements
def log_info(message: str, module: str = "main") -> None:
    """Log info message (replaces print() statements)."""
    get_logger(module).info(message)


def log_warning(message: str, module: str = "main") -> None:
    """Log warning message (replaces print("[WARNING] ...") statements)."""
    get_logger(module).warning(message)


def log_error(message: str, module: str = "main", exc_info: bool = False) -> None:
    """Log error message (replaces print("[ERROR] ...") statements)."""
    get_logger(module).error(message, exc_info=exc_info)


def log_debug(message: str, module: str = "main") -> None:
    """Log debug message (replaces print("[DEBUG] ...") statements)."""
    get_logger(module).debug(message)


# Example usage for developers
if __name__ == "__main__":
    # Setup logging with file output
    CorreXLogger.setup(
        level=logging.DEBUG,
        log_file=Path("correx_debug.log"),
        console=True
    )
    
    # Get logger for a module
    logger = get_logger("example_module")
    
    # Log at different levels
    logger.debug("Debug information")
    logger.info("Informational message")
    logger.warning("Warning message")
    logger.error("Error occurred")
    
    # Log with exception info
    try:
        raise ValueError("Example error")
    except ValueError:
        logger.error("Caught exception", exc_info=True)
