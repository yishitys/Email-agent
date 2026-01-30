"""
SkillEmailNormalize - 邮件归一化

将 Gmail 邮件转换为统一的数据结构
"""
import re
from typing import Optional
from html import unescape

from app.core.schemas import NormalizedEmail
from app.integrations.gmail.fetch import MessageSummary
from app.core.logging import get_logger

logger = get_logger(__name__)


class SkillEmailNormalize:
    """
    邮件归一化技能

    将邮件转换为统一格式
    """

    @staticmethod
    def normalize(message: MessageSummary) -> NormalizedEmail:
        """
        归一化邮件

        Args:
            message: MessageSummary 对象

        Returns:
            NormalizedEmail 对象
        """
        try:
            # 使用完整正文或 snippet
            body_plain = SkillEmailNormalize._clean_text(message.body_plain or message.snippet)

            # 清理主题
            subject = SkillEmailNormalize._clean_subject(message.subject) if message.subject else "无主题"

            # 提取发件人姓名和域名
            sender_name = SkillEmailNormalize._extract_name(message.from_addr)
            sender_domain = SkillEmailNormalize._extract_domain(message.from_addr)

            # 提取邮箱地址
            from_email = SkillEmailNormalize._extract_email(message.from_addr)
            to_email = SkillEmailNormalize._extract_email(message.to_addr)

            # 处理 CC 列表
            cc_emails = [SkillEmailNormalize._extract_email(cc) for cc in message.cc_addrs]
            cc_emails = [cc for cc in cc_emails if cc]  # 过滤空值

            # 附件信息
            has_attachments = len(message.attachment_names) > 0

            return NormalizedEmail(
                message_id=message.id,
                thread_id=message.thread_id,
                subject=subject,
                from_addr=from_email,
                to_addr=to_email,
                date=message.date,
                body_plain=body_plain,
                snippet=message.snippet,
                labels=message.labels,
                lang=None,  # 语言检测可选，暂不实现
                sender_name=sender_name,
                sender_domain=sender_domain,
                cc_addrs=cc_emails,
                has_attachments=has_attachments,
                attachment_names=message.attachment_names
            )

        except Exception as e:
            logger.error(f"归一化邮件 {message.id} 失败: {e}")
            # 失败时返回最小化的数据
            return NormalizedEmail(
                message_id=message.id,
                thread_id=message.thread_id,
                subject="解析失败",
                from_addr=None,
                to_addr=None,
                date=message.date,
                body_plain=message.snippet or "",
                snippet=message.snippet or "",
                labels=message.labels
            )

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """
        清理文本

        去除 HTML 标签、多余空白等

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""

        # HTML 解码
        text = unescape(text)

        # 去除 HTML 标签（简单处理）
        text = re.sub(r'<[^>]+>', '', text)

        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)

        # 去除首尾空白
        text = text.strip()

        return text

    @staticmethod
    def _clean_subject(subject: str) -> str:
        """
        清理主题

        去除 Re:, Fwd: 等前缀

        Args:
            subject: 原始主题

        Returns:
            清理后的主题
        """
        # 去除常见前缀
        subject = re.sub(r'^(Re|RE|Fwd|FWD|Fw|FW):\s*', '', subject, flags=re.IGNORECASE)

        # 去除多余空白
        subject = re.sub(r'\s+', ' ', subject).strip()

        return subject

    @staticmethod
    def _extract_email(addr: Optional[str]) -> Optional[str]:
        """
        从地址字符串中提取邮箱

        例如: "张三 <zhangsan@example.com>" -> "zhangsan@example.com"

        Args:
            addr: 地址字符串

        Returns:
            邮箱地址
        """
        if not addr:
            return None

        # 尝试提取 <email@domain.com> 格式
        match = re.search(r'<([^>]+)>', addr)
        if match:
            return match.group(1)

        # 如果没有尖括号，检查是否是纯邮箱
        if '@' in addr:
            # 简单验证
            parts = addr.strip().split()
            for part in parts:
                if '@' in part:
                    return part

        return addr.strip()

    @staticmethod
    def _extract_name(addr: Optional[str]) -> Optional[str]:
        """
        从地址字符串中提取姓名

        例如: "张三 <zhangsan@example.com>" -> "张三"
             "zhangsan@example.com" -> None

        Args:
            addr: 地址字符串

        Returns:
            姓名（如果有）
        """
        if not addr:
            return None

        # 尝试提取 "Name <email>" 格式中的 Name
        match = re.match(r'^(.+?)\s*<[^>]+>$', addr)
        if match:
            name = match.group(1).strip()
            # 去除可能的引号
            name = name.strip('"').strip("'")
            return name if name else None

        # 如果是纯邮箱格式，返回 None
        if '@' in addr:
            return None

        return addr.strip()

    @staticmethod
    def _extract_domain(addr: Optional[str]) -> Optional[str]:
        """
        从地址字符串中提取域名

        例如: "张三 <zhangsan@example.com>" -> "example.com"
             "zhangsan@example.com" -> "example.com"

        Args:
            addr: 地址字符串

        Returns:
            域名（如果有）
        """
        email = SkillEmailNormalize._extract_email(addr)
        if not email or '@' not in email:
            return None

        try:
            domain = email.split('@')[1]
            return domain.lower()
        except:
            return None
