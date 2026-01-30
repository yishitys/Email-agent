"""
日志配置模块
提供统一的日志配置和敏感信息脱敏功能
"""
import logging
import re
import sys
from typing import Any

from app.core.config import config


class SensitiveDataFilter(logging.Filter):
    """
    日志过滤器，自动脱敏敏感信息
    """

    # 需要脱敏的模式
    SENSITIVE_PATTERNS = [
        # OpenAI API Keys (sk-proj-..., sk-..., 等) - 必须在通用规则之前
        (r'sk[-_][a-zA-Z0-9\-_]{20,}', r'***'),
        # Bearer tokens
        (r'(Bearer\s+)([a-zA-Z0-9\-._~+/]+)', r'\1***'),
        # 通用 token/key/password/secret 模式（支持下划线和等号）
        (r'(["\']?(?:token|key|password|secret|api[_-]?key|OPENAI_API_KEY)["\']?\s*[:=]\s*["\']?)([^"\'\\s,]+)', r'\1***'),
        # OAuth token
        (r'(access[_-]?token["\']?\s*[:=]\s*["\']?)([^"\'\\s,]+)', r'\1***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录，脱敏敏感信息

        Args:
            record: 日志记录

        Returns:
            是否保留该日志记录
        """
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)

        if record.args:
            record.args = tuple(
                self._sanitize(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )

        return True

    def _sanitize(self, text: str) -> str:
        """
        脱敏文本中的敏感信息

        Args:
            text: 原始文本

        Returns:
            脱敏后的文本
        """
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text


def setup_logging(level: str = None) -> None:
    """
    配置应用日志

    Args:
        level: 日志级别，默认从配置读取
    """
    log_level = level or config.LOG_LEVEL

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 设置日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # 添加敏感数据过滤器
    console_handler.addFilter(SensitiveDataFilter())

    # 添加处理器到根记录器
    root_logger.addHandler(console_handler)

    # 设置第三方库的日志级别（避免过多输出）
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器

    Args:
        name: 日志记录器名称，通常使用 __name__

    Returns:
        日志记录器实例
    """
    return logging.getLogger(name)


# 应用启动时自动配置日志
setup_logging()
