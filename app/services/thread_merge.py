"""
SkillThreadMerge - 线程合并

按 thread_id 聚合邮件，生成线程上下文
"""
from collections import defaultdict
from typing import List

from app.core.schemas import NormalizedEmail, ThreadContext
from app.core.logging import get_logger

logger = get_logger(__name__)

# 最大合并文本长度（字符数）
MAX_COMBINED_LENGTH = 12000


class SkillThreadMerge:
    """
    线程合并技能

    将同一线程的邮件聚合在一起
    """

    @staticmethod
    def merge_threads(emails: List[NormalizedEmail]) -> List[ThreadContext]:
        """
        按线程合并邮件

        Args:
            emails: 归一化的邮件列表

        Returns:
            线程上下文列表
        """
        if not emails:
            logger.info("没有邮件需要合并")
            return []

        # 按 thread_id 分组
        threads = defaultdict(list)
        for email in emails:
            threads[email.thread_id].append(email)

        logger.info(f"共 {len(emails)} 封邮件，分为 {len(threads)} 个线程")

        # 为每个线程创建上下文
        contexts = []
        for thread_id, thread_emails in threads.items():
            context = SkillThreadMerge._create_thread_context(
                thread_id,
                thread_emails
            )
            contexts.append(context)

        # 按最新邮件时间排序（最新的在前）
        contexts.sort(
            key=lambda c: max((m.date for m in c.messages if m.date), default=None) or 0,
            reverse=True
        )

        return contexts

    @staticmethod
    def _create_thread_context(
        thread_id: str,
        emails: List[NormalizedEmail]
    ) -> ThreadContext:
        """
        创建单个线程的上下文

        Args:
            thread_id: 线程 ID
            emails: 线程中的邮件列表

        Returns:
            ThreadContext 对象
        """
        # 按时间排序（早的在前）
        sorted_emails = sorted(
            emails,
            key=lambda e: e.date if e.date else 0
        )

        # 使用第一封邮件的主题
        subject = sorted_emails[0].subject if sorted_emails else "无主题"

        # 计算线程元数据
        participants = set()
        sender_domains = set()
        has_attachments = False
        latest_date = None

        for email in sorted_emails:
            # 收集参与者
            if email.from_addr:
                participants.add(email.from_addr)
            if email.to_addr:
                participants.add(email.to_addr)
            for cc in email.cc_addrs:
                participants.add(cc)

            # 收集发件人域名
            if email.sender_domain:
                sender_domains.add(email.sender_domain)

            # 检查附件
            if email.has_attachments:
                has_attachments = True

            # 记录最新日期
            if email.date and (latest_date is None or email.date > latest_date):
                latest_date = email.date

        # 合并文本
        combined_parts = []
        total_length = 0
        is_truncated = False

        for i, email in enumerate(sorted_emails):
            # 构建单封邮件的文本（包含发件人姓名）
            sender_display = email.sender_name if email.sender_name else email.from_addr or '未知'

            # 附件标识
            attachment_info = ""
            if email.has_attachments:
                if len(email.attachment_names) > 0:
                    attachment_info = f"\n📎 附件: {', '.join(email.attachment_names[:3])}"
                    if len(email.attachment_names) > 3:
                        attachment_info += f" (还有 {len(email.attachment_names) - 3} 个)"
                else:
                    attachment_info = "\n📎 包含附件"

            email_text = f"""
邮件 {i + 1}:
发件人: {sender_display} ({email.from_addr or '未知'})
时间: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else '未知'}{attachment_info}
内容: {email.body_plain}
---
""".strip()

            # 检查长度
            if total_length + len(email_text) > MAX_COMBINED_LENGTH:
                # 超过最大长度，截断
                remaining = MAX_COMBINED_LENGTH - total_length
                if remaining > 100:  # 至少保留 100 字符
                    combined_parts.append(email_text[:remaining] + "...")
                combined_parts.append(f"\n[线程过长，剩余 {len(sorted_emails) - i} 封邮件已省略]")
                is_truncated = True
                break

            combined_parts.append(email_text)
            total_length += len(email_text)

        combined_text = "\n\n".join(combined_parts)

        return ThreadContext(
            thread_id=thread_id,
            subject=subject,
            messages=sorted_emails,
            combined_text=combined_text,
            is_truncated=is_truncated,
            participants=list(participants),
            sender_domains=sender_domains,
            has_attachments=has_attachments,
            total_messages=len(sorted_emails),
            latest_date=latest_date
        )
