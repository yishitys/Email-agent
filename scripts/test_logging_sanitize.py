"""
测试日志脱敏功能的详细测试
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.logging import get_logger

logger = get_logger(__name__)

print("=" * 60)
print("详细的敏感信息脱敏测试")
print("=" * 60)
print()

test_cases = [
    "sk-1234567890abcdefghijklmnopqrstuvwxyz",
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    "api_key=sk-test123456789012345678901234567890",
    "api_key: sk-test123456789012345678901234567890",
    '"api_key": "secret_value_12345"',
    "token='ya29.a0ARrdaM-secret-token'",
    "password=mySecretPassword123",
    "secret: my_secret_value",
    "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456",
]

for i, test_case in enumerate(test_cases, 1):
    logger.info(f"测试 {i}: {test_case}")

print()
print("=" * 60)
print("如果看到明文敏感信息，说明脱敏规则需要改进")
print("=" * 60)
