"""
测试邮件处理管道 (Step 5-9)
"""
import sys
from pathlib import Path
from datetime import date, datetime
from unittest.mock import Mock

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.integrations.gmail.fetch import MessageSummary
from app.integrations.gmail.normalize import SkillEmailNormalize
from app.services.thread_merge import SkillThreadMerge
from app.services.importance import SkillImportanceHeuristics
from app.integrations.openai.prompts import SkillPromptCompose
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_pipeline():
    """测试完整的邮件处理管道"""
    print("=" * 60)
    print("邮件处理管道测试 (Step 5-9)")
    print("=" * 60)
    print()

    # 创建模拟邮件数据
    print("步骤 1: 创建模拟邮件数据")
    print("-" * 60)

    mock_messages = [
        MessageSummary(
            id="msg_001",
            thread_id="thread_001",
            subject="紧急：项目进度会议",
            from_addr="Boss <boss@company.com>",
            to_addr="me@company.com",
            date=datetime(2026, 1, 30, 9, 0, 0),
            snippet="请准备下周的项目进度汇报，包括当前进展、遇到的问题和下一步计划...",
            labels=["IMPORTANT", "UNREAD", "INBOX"]
        ),
        MessageSummary(
            id="msg_002",
            thread_id="thread_001",
            subject="Re: 紧急：项目进度会议",
            from_addr="Colleague <colleague@company.com>",
            to_addr="me@company.com",
            date=datetime(2026, 1, 30, 10, 30, 0),
            snippet="我已经准备好了技术部分的材料，可以分享给你...",
            labels=["INBOX"]
        ),
        MessageSummary(
            id="msg_003",
            thread_id="thread_002",
            subject="账单通知：1月份云服务费用",
            from_addr="AWS <billing@aws.com>",
            to_addr="me@company.com",
            date=datetime(2026, 1, 30, 8, 0, 0),
            snippet="您的1月份 AWS 使用费用为 $1,234.56，请查收账单...",
            labels=["INBOX"]
        ),
        MessageSummary(
            id="msg_004",
            thread_id="thread_003",
            subject="LinkedIn: 你有新的连接请求",
            from_addr="LinkedIn <notifications@linkedin.com>",
            to_addr="me@personal.com",
            date=datetime(2026, 1, 30, 7, 0, 0),
            snippet="张三想与你建立连接...",
            labels=["INBOX", "SOCIAL"]
        ),
    ]

    print(f"✓ 创建了 {len(mock_messages)} 封模拟邮件")
    print()

    # Step 6: 归一化
    print("步骤 2: 归一化邮件 (Step 6)")
    print("-" * 60)

    normalized_emails = []
    for msg in mock_messages:
        normalized = SkillEmailNormalize.normalize(msg)
        normalized_emails.append(normalized)

    print(f"✓ 归一化了 {len(normalized_emails)} 封邮件")
    for email in normalized_emails[:2]:
        print(f"  - {email.subject[:40]}... (from: {email.from_addr})")
    print()

    # Step 7: 线程合并
    print("步骤 3: 线程合并 (Step 7)")
    print("-" * 60)

    threads = SkillThreadMerge.merge_threads(normalized_emails)

    print(f"✓ 合并为 {len(threads)} 个线程")
    for thread in threads:
        print(f"  - {thread.subject} ({len(thread.messages)} 封邮件)")
        if thread.is_truncated:
            print(f"    [已截断]")
    print()

    # Step 8: 重要性评分
    print("步骤 4: 重要性评分 (Step 8)")
    print("-" * 60)

    scorer = SkillImportanceHeuristics()
    scored_threads = scorer.prioritize_threads(threads)

    print(f"✓ 为 {len(scored_threads)} 个线程评分")
    for thread, score in scored_threads:
        priority = scorer.get_priority_label(score)
        print(f"  - [{priority}] {thread.subject}: {score:.1f}分")
    print()

    # Step 9: Prompt 构建
    print("步骤 5: Prompt 构建 (Step 9)")
    print("-" * 60)

    system_prompt, user_prompt = SkillPromptCompose.compose(
        scored_threads,
        date(2026, 1, 30)
    )

    print(f"✓ Prompt 已构建")
    print(f"  System prompt 长度: {len(system_prompt)} 字符")
    print(f"  User prompt 长度: {len(user_prompt)} 字符")
    print()
    print("System Prompt 预览:")
    print(system_prompt[:200] + "...")
    print()
    print("User Prompt 预览:")
    print(user_prompt[:300] + "...")
    print()

    # Step 9: GPT 调用（仅测试初始化，不实际调用）
    print("步骤 6: GPT 初始化 (Step 9)")
    print("-" * 60)

    from app.core.config import config
    if config.OPENAI_API_KEY:
        try:
            from app.integrations.openai.summarize import SkillGptSummarize
            gpt = SkillGptSummarize()
            print("✓ GPT 客户端初始化成功")
            print(f"  模型: {gpt.model}")
            print()
            print("⚠ 注意：实际 GPT 调用需要有效的 API key 和网络连接")
            print("  若要测试完整功能，请确保 .env 中配置了 OPENAI_API_KEY")
        except Exception as e:
            print(f"✗ GPT 初始化失败: {e}")
    else:
        print("⚠ 未配置 OPENAI_API_KEY，跳过 GPT 初始化")
    print()

    print("=" * 60)
    print("管道测试完成！")
    print("=" * 60)
    print()
    print("总结:")
    print(f"  ✓ Step 5: Gmail 拉取 - 模拟数据已准备")
    print(f"  ✓ Step 6: 邮件归一化 - {len(normalized_emails)} 封邮件")
    print(f"  ✓ Step 7: 线程合并 - {len(threads)} 个线程")
    print(f"  ✓ Step 8: 重要性评分 - 已完成")
    print(f"  ✓ Step 9: OpenAI 集成 - Prompt 已构建")
    print()


if __name__ == "__main__":
    test_pipeline()
