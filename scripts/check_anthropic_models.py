"""
检查 Anthropic API 可用模型
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print()
print("=" * 60)
print("检查 Claude API 账号状态")
print("=" * 60)
print()

from anthropic import Anthropic
from app.core.config import config

# 尝试不同的模型
models_to_try = [
    "claude-3-5-sonnet-latest",
    "claude-3-opus-latest",
    "claude-3-sonnet-latest",
    "claude-3-haiku-20240307",
    "claude-2.1",
]

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

print("API Key: (已配置) ✅" if config.ANTHROPIC_API_KEY else "API Key: (未配置) ❌")
print()

for model in models_to_try:
    try:
        print(f"尝试模型: {model}")
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": "hi"}]
        )
        print(f"  ✓ 成功！使用此模型: {model}")
        print(f"  响应: {response.content[0].text[:50]}...")
        print()

        # 找到可用模型，退出
        print(f"建议使用模型: {model}")
        break

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "not_found" in error_msg:
            print(f"  ✗ 模型不可用")
        elif "401" in error_msg or "authentication" in error_msg.lower():
            print(f"  ✗ API key 无效")
            break
        elif "permission" in error_msg.lower():
            print(f"  ✗ 权限不足")
        else:
            print(f"  ✗ 错误: {error_msg[:100]}")
        print()

print("=" * 60)
