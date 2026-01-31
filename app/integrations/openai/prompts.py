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
        system_prompt = """你是一个专业的邮件助手，负责分析邮件并生成每日报告。

**核心规则**：根据每个线程标题中的「重要性」分数区分处理：
- **重要性分数 >= 20** 的线程视为「重要邮件」，输出到「重要邮件」章节。
- **重要性分数 < 20** 的线程视为「非重要邮件」，输出到「非重要邮件」章节。

请用中文 Markdown 格式生成报告，必须包含以下章节（顺序不可变）：

## 📧 重要邮件

仅包含重要性分数 >= 20 的线程。每条**只允许**以下 3 个字段，不得添加「为什么重要」「建议行动」「附件」等任何其他字段：

**[邮件主题]**
- **发件人**: 姓名 (邮箱)
- **时间**: YYYY-MM-DD HH:MM
- **内容摘要**: 2-3句话概括邮件的主要内容

## 📋 非重要邮件

仅包含重要性分数 < 20 的线程。每条**只允许**：发件人 + 一句话内容摘要，**不得**包含时间或其它字段。格式：

**[邮件主题]** — **发件人**: 姓名 (邮箱)。一句话摘要。

## ⚡ 今日重点

3-5条最关键的发现或待办事项（从重要邮件中提炼）

## ✅ 行动清单

具体的待办事项列表

---

**重要邮件输出示例**（仅 3 字段）：

**验证您的邮件地址**
- **发件人**: Anthropic Support Team (noreply@anthropic.com)
- **时间**: 2026-01-30 09:15
- **内容摘要**: Anthropic 要求验证邮箱地址以完成账户设置。邮件中包含验证链接，需要点击以激活账户的支付功能。如果24小时内未验证，将无法使用某些服务。

**非重要邮件输出示例**（发件人 + 一句话）：

**促销活动** — **发件人**: 某品牌 (promo@brand.com)。推广本月折扣，无需行动。"""

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

        user_parts.append("请按照系统提示词中的格式要求生成报告。")
        user_parts.append("")
        user_parts.append("重要约束:")
        user_parts.append("- 根据每个线程标题中的「重要性」分数判断：分数 >= 20 的放入「重要邮件」章节，分数 < 20 的放入「非重要邮件」章节。")
        user_parts.append("- 重要邮件每条只允许 3 个字段：发件人、时间、内容摘要；不得添加「为什么重要」「建议行动」「附件」等任何其它字段。")
        user_parts.append("- 非重要邮件每条必须只有一句话摘要（发件人 + 一句话内容），不得包含时间或其它小节。")

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
