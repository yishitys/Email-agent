"""
测试 Claude API 连接
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print()
print("=" * 60)
print("测试 Claude API 连接")
print("=" * 60)
print()

try:
    from app.integrations.anthropic.summarize import SkillClaudeSummarize

    print("1. 初始化 Claude 客户端...")
    claude = SkillClaudeSummarize()
    print(f"   ✓ 客户端初始化成功")
    print(f"   模型: {claude.model}")
    print()

    print("2. 发送测试请求...")
    response = claude.summarize(
        system_prompt="你是一个测试助手。",
        user_prompt="请用 JSON 格式返回: {\"status\": \"ok\", \"message\": \"连接成功！\"}"
    )
    print(f"   ✓ API 调用成功")
    print(f"   响应: {response}")
    print()

    print("=" * 60)
    print("✅ Claude API 连接正常！")
    print("=" * 60)
    print()

except Exception as e:
    print(f"   ✗ 错误: {e}")
    print()
    print("=" * 60)
    print("❌ 连接失败")
    print("=" * 60)
    print()
    sys.exit(1)
