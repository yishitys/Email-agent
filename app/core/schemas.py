"""
数据模式定义

统一的数据结构
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class NormalizedEmail:
    """
    归一化的邮件数据

    统一的邮件表示，便于后续处理
    """
    # Gmail 标识
    message_id: str
    thread_id: str

    # 邮件元数据
    subject: Optional[str]
    from_addr: Optional[str]
    to_addr: Optional[str]
    date: Optional[datetime]

    # 邮件内容
    body_plain: str  # 纯文本正文
    snippet: str     # 摘要片段

    # 附加信息
    labels: List[str]
    lang: Optional[str] = None  # 语言（可选）

    # 扩展字段
    sender_name: Optional[str] = None      # 发件人姓名
    sender_domain: Optional[str] = None    # 发件人域名
    cc_addrs: List[str] = None             # 抄送人列表
    has_attachments: bool = False          # 是否有附件
    attachment_names: List[str] = None     # 附件文件名列表

    def __post_init__(self):
        """初始化默认值"""
        if self.cc_addrs is None:
            self.cc_addrs = []
        if self.attachment_names is None:
            self.attachment_names = []

    def to_dict(self):
        """转换为字典"""
        return {
            'message_id': self.message_id,
            'thread_id': self.thread_id,
            'subject': self.subject,
            'from_addr': self.from_addr,
            'to_addr': self.to_addr,
            'date': self.date.isoformat() if self.date else None,
            'body_plain': self.body_plain,
            'snippet': self.snippet,
            'labels': self.labels,
            'lang': self.lang,
            'sender_name': self.sender_name,
            'sender_domain': self.sender_domain,
            'cc_addrs': self.cc_addrs,
            'has_attachments': self.has_attachments,
            'attachment_names': self.attachment_names
        }


@dataclass
class ThreadContext:
    """
    线程上下文

    按 thread_id 聚合的邮件集合
    """
    thread_id: str
    subject: str
    messages: List[NormalizedEmail]  # 按时间排序的邮件列表
    combined_text: str  # 合并的文本（用于 GPT）
    is_truncated: bool = False  # 是否因为太长而被截断

    # 扩展字段
    participants: List[str] = None         # 所有参与者
    sender_domains: set = None             # 发件人域名集合
    has_attachments: bool = False          # 线程是否有附件
    total_messages: int = 0                # 消息总数
    latest_date: Optional[datetime] = None # 最新消息时间

    def __post_init__(self):
        """初始化默认值"""
        if self.participants is None:
            self.participants = []
        if self.sender_domains is None:
            self.sender_domains = set()

    def to_dict(self):
        """转换为字典"""
        return {
            'thread_id': self.thread_id,
            'subject': self.subject,
            'messages': [m.to_dict() for m in self.messages],
            'combined_text': self.combined_text,
            'is_truncated': self.is_truncated,
            'participants': self.participants,
            'sender_domains': list(self.sender_domains) if self.sender_domains else [],
            'has_attachments': self.has_attachments,
            'total_messages': self.total_messages,
            'latest_date': self.latest_date.isoformat() if self.latest_date else None
        }
