"""
测试配置和日志模块
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import config
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_config():
    """测试配置读取"""
    print("=" * 60)
    print("配置测试")
    print("=" * 60)

    # 显示安全的配置信息
    print("\n安全配置信息（已脱敏）:")
    for key, value in config.get_safe_config().items():
        print(f"  {key}: {value}")

    # 验证必需配置
    print("\n配置验证:")
    missing = config.validate()
    if missing:
        print(f"  ⚠ 缺失的配置项: {', '.join(missing)}")
    else:
        print("  ✓ 所有必需配置项已设置")

    print()


def test_logging():
    """测试日志功能和敏感信息脱敏"""
    print("=" * 60)
    print("日志测试")
    print("=" * 60)
    print()

    # 测试不同级别的日志
    logger.debug("这是一条 DEBUG 日志")
    logger.info("这是一条 INFO 日志")
    logger.warning("这是一条 WARNING 日志")
    logger.error("这是一条 ERROR 日志")

    # 测试敏感信息脱敏
    print("\n敏感信息脱敏测试:")
    print("（以下日志中的敏感信息应该被自动脱敏）")
    logger.info("API Key: sk-1234567890abcdefghijklmnopqrstuvwxyz")
    logger.info("Bearer token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    logger.info("Config: api_key=secret_key_12345")
    logger.info("Token: access_token='ya29.a0ARrdaM-secret-token'")

    print()


if __name__ == "__main__":
    test_config()
    test_logging()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)
