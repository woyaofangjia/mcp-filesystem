import logging
import json
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """结构化JSON日志格式"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class Logger:
    """企业级日志系统

    支持分级日志、JSON结构化输出、日志轮转、持久化存储。
    """

    _instances: Dict[str, "Logger"] = {}

    def __init__(
        self,
        name: str = "filesystem-mcp",
        level: str = "INFO",
        log_dir: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        console: bool = True,
    ):
        self.name = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.handlers.clear()

        formatter = JSONFormatter()

        if console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{name}.log")
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def _log(
        self,
        level: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
    ) -> None:
        extra = {}
        if data:
            extra["extra_data"] = data
        self._logger.log(level, message, exc_info=exc_info, extra=extra)

    def debug(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.DEBUG, message, data)

    def info(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.INFO, message, data)

    def warning(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.WARNING, message, data)

    def error(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
    ) -> None:
        self._log(logging.ERROR, message, data, exc_info)

    def critical(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
    ) -> None:
        self._log(logging.CRITICAL, message, data, exc_info)

    def set_level(self, level: str) -> None:
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(
    name: str = "filesystem-mcp",
    level: str = "INFO",
    log_dir: Optional[str] = None,
) -> Logger:
    """获取或创建Logger单例"""
    if name not in Logger._instances:
        Logger._instances[name] = Logger(name=name, level=level, log_dir=log_dir)
    return Logger._instances[name]
