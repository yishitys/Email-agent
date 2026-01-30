"""
配置管理模块
从环境变量读取配置，提供统一的配置访问接口
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    """应用配置类"""

    # AI 提供商配置
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "claude")  # "openai" 或 "claude"

    # OpenAI 配置
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Anthropic Claude 配置
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # 应用配置
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

    # Gmail 配置
    # credentials.json 路径，优先查找项目根目录，其次是 data/ 目录
    _credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
    if _credentials_path:
        GMAIL_CREDENTIALS_PATH = Path(_credentials_path)
    else:
        # 默认路径查找顺序
        project_root = Path(__file__).parent.parent.parent
        if (project_root / "credentials.json").exists():
            GMAIL_CREDENTIALS_PATH = project_root / "credentials.json"
        elif (project_root / "data" / "credentials.json").exists():
            GMAIL_CREDENTIALS_PATH = project_root / "data" / "credentials.json"
        else:
            GMAIL_CREDENTIALS_PATH = project_root / "credentials.json"  # 默认位置

    # Token 存储路径
    GMAIL_TOKEN_PATH: Path = Path(os.getenv(
        "GMAIL_TOKEN_PATH",
        Path(__file__).parent.parent.parent / "data" / "token.json"
    ))

    # 数据库配置
    DATABASE_PATH: Path = Path(os.getenv(
        "DATABASE_PATH",
        Path(__file__).parent.parent.parent / "data" / "reports.db"
    ))

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def get_safe_config(cls) -> dict:
        """
        获取安全的配置信息（脱敏后），用于日志或调试
        """
        return {
            "AI_PROVIDER": cls.AI_PROVIDER,
            "OPENAI_MODEL": cls.OPENAI_MODEL,
            "OPENAI_API_KEY": cls._mask_sensitive(cls.OPENAI_API_KEY),
            "ANTHROPIC_MODEL": cls.ANTHROPIC_MODEL,
            "ANTHROPIC_API_KEY": cls._mask_sensitive(cls.ANTHROPIC_API_KEY),
            "APP_BASE_URL": cls.APP_BASE_URL,
            "GMAIL_CREDENTIALS_PATH": str(cls.GMAIL_CREDENTIALS_PATH),
            "GMAIL_TOKEN_PATH": str(cls.GMAIL_TOKEN_PATH),
            "DATABASE_PATH": str(cls.DATABASE_PATH),
            "LOG_LEVEL": cls.LOG_LEVEL,
        }

    @staticmethod
    def _mask_sensitive(value: Optional[str], show_chars: int = 4) -> str:
        """
        脱敏处理敏感信息

        Args:
            value: 原始值
            show_chars: 显示的字符数

        Returns:
            脱敏后的字符串
        """
        if not value:
            return "<未设置>"
        if len(value) <= show_chars:
            return "***"
        return f"{value[:show_chars]}...{value[-show_chars:]}"

    @classmethod
    def validate(cls) -> list[str]:
        """
        验证必需的配置项

        Returns:
            缺失的配置项列表
        """
        missing = []

        # 检查 AI API key
        if cls.AI_PROVIDER == "openai":
            if not cls.OPENAI_API_KEY:
                missing.append("OPENAI_API_KEY")
        elif cls.AI_PROVIDER == "claude":
            if not cls.ANTHROPIC_API_KEY:
                missing.append("ANTHROPIC_API_KEY")

        return missing


# 全局配置实例
config = Config()
