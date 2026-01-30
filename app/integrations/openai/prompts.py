"""
SkillPromptCompose - Prompt 构建

根据邮件生成稳定的 GPT prompt
"""
from typing import List, Tuple
from datetime import date

from app.core.schemas import ThreadContext
from app.core.logging import get_logger

logger = get_logger(__name__)


class SkillPromptCompose:
    """
    Prompt 构建技能

    生成用于 GPT 的 system 和 user prompt
    """

    @staticmethod
    def compose(
        threads: List[Tuple[ThreadContext, float]],
        report_date: date
    ) -> Tuple[str, str]:
        """
        构建 prompt

        Args:
            threads: (线程, 重要性分数) 列表
            report_date: 报告日期

        Returns:
            (system_prompt, user_prompt) 元组
        """
        # 检查是否有邮件
        if not threads:
            logger.info("没有邮件，返回空报告 prompt")
            return SkillPromptCompose._empty_prompt(report_date)

        # 构建 system prompt
        system_prompt = """你是一个专业的邮件助手，负责分析邮件并生成详细的每日报告。

**核心原则**：邮件内容是报告的核心。你必须为每封重要邮件提供详细的信息，而不仅仅是列出标题。

请用中文 Markdown 格式生成报告，包含以下章节：

## 📧 今日邮件详情

对每封重要邮件（按优先级排序），必须包含以下信息：

**[邮件主题]**
- **发件人**: 姓名 (邮箱)
- **时间**: YYYY-MM-DD HH:MM
- **内容摘要**: 2-3句话概括邮件的主要内容（这是最重要的部分！）
- **为什么重要**: 说明这封邮件需要关注的原因
- **建议行动**: 具体的下一步操作，包含时间建议（如"今天"、"本周内"）
- **附件**: 如有附件，列出说明

## ⚡ 今日重点

3-5条最关键的发现或待办事项（从上述邮件中提炼）

## ✅ 行动清单

具体的待办事项列表

---

**输出格式示例**：

**验证您的邮件地址**
- **发件人**: Anthropic Support Team (noreply@anthropic.com)
- **时间**: 2026-01-30 09:15
- **内容摘要**: Anthropic 要求验证邮箱地址以完成账户设置。邮件中包含验证链接，需要点击以激活账户的支付功能。如果24小时内未验证，将无法使用某些服务。
- **为什么重要**: 账户功能受限，可能影响正常使用
- **建议行动**: 立即点击邮件中的验证链接（今天完成）
- **附件**: 无

**项目进度汇报提醒**
- **发件人**: 张三 / Boss (boss@company.com)
- **时间**: 2026-01-30 10:30
- **内容摘要**: 老板提醒下周一需要提交Q1项目进度汇报。要求包含预算执行情况、关键里程碑达成情况和Q2规划。会议时间定在下周一上午10点。
- **为什么重要**: 来自上级的直接要求，涉及季度考核
- **建议行动**: 本周五前准备初稿，周末完善，周一早上最终审核（deadline：下周一10:00）
- **附件**: 📎 Q1_Report_Template.xlsx

**重要**：
- 必须为每封邮件提供"内容摘要"，这是报告的核心价值
- 不要只列出邮件标题，要说明邮件具体说了什么
- 内容摘要应该让读者无需打开邮件就能了解关键信息"""

        # 构建 user prompt
        user_parts = [
            f"请分析 {report_date.strftime('%Y年%m月%d日')} 的邮件，生成每日报告。",
            "",
            f"共 {len(threads)} 个邮件线程：",
            ""
        ]

        # 添加每个线程（限制数量避免超长）
        max_threads = 50  # 最多包含 50 个线程
        for i, (thread, score) in enumerate(threads[:max_threads], 1):
            user_parts.append(f"### 线程 {i} (重要性: {score:.1f})")
            user_parts.append(f"主题: {thread.subject}")
            user_parts.append(f"邮件数: {thread.total_messages}")

            # 参与者信息
            if thread.participants:
                user_parts.append(f"参与者: {', '.join(thread.participants[:3])}")
                if len(thread.participants) > 3:
                    user_parts.append(f"  (还有 {len(thread.participants) - 3} 人)")

            # 附件标识
            if thread.has_attachments:
                user_parts.append("📎 包含附件")

            # 完整内容（不截断到 500 字符）
            user_parts.append(f"内容:\n{thread.combined_text}")
            user_parts.append("")

        if len(threads) > max_threads:
            user_parts.append(f"(还有 {len(threads) - max_threads} 个线程已省略)")
            user_parts.append("")

        user_parts.append("请按照系统提示词中的格式要求，为每封邮件生成详细的报告。")
        user_parts.append("")
        user_parts.append("重要提示:")
        user_parts.append("- 必须为每封邮件提供详细的内容摘要（2-3句话）")
        user_parts.append("- 内容摘要应该说明邮件的具体内容，而不仅仅是主题")
        user_parts.append("- 让读者无需打开邮件就能了解关键信息")

        user_prompt = "\n".join(user_parts)

        logger.info(f"Prompt 已构建：{len(threads)} 个线程，user prompt 长度 {len(user_prompt)}")
        return system_prompt, user_prompt

    @staticmethod
    def _empty_prompt(report_date: date) -> Tuple[str, str]:
        """
        生成空报告的 prompt

        Args:
            report_date: 报告日期

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = "你是一个邮件助手。"
        user_prompt = f"""
{report_date.strftime('%Y年%m月%d日')} 没有新邮件。

请生成简短的 Markdown 格式报告。
"""
        return system_prompt, user_prompt
