"""
Logging utilities for MateBot
"""

import sys
from pathlib import Path
from loguru import logger
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file: str = "logs/matebot.log",
    max_size_mb: int = 50,
    backup_count: int = 5
) -> None:
    """
    Configure logging for the robot
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_file: Path to log file
        max_size_mb: Maximum log file size in MB before rotation
        backup_count: Number of backup files to keep
    """
    # Remove default handler
    logger.remove()
    
    # Console handler with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # File handler with rotation
    if log_to_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation=f"{max_size_mb} MB",
            retention=backup_count,
            compression="zip"
        )
    
    logger.info(f"Logging initialized (level={log_level}, file={log_to_file})")


def create_session_logger(session_name: str) -> None:
    """
    Create a separate logger for a specific session
    
    Args:
        session_name: Name of the session (e.g., mapping session, task execution)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = f"logs/sessions/{session_name}_{timestamp}.log"
    
    Path(session_file).parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        session_file,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
        level="DEBUG",
        filter=lambda record: record["extra"].get("session") == session_name
    )
    
    logger.bind(session=session_name).info(f"Session logger created: {session_name}")
