"""
SkillImportanceHeuristics - 重要性评分

基于规则的邮件重要性评分
"""
from typing import List, Dict
import re

from app.core.schemas import NormalizedEmail, ThreadContext
from app.core.logging import get_logger

logger = get_logger(__name__)

# 默认评分规则
DEFAULT_RULES = {
    # 标签权重
    'labels': {
        'IMPORTANT': 5,
        'STARRED': 10,
        'UNREAD': 3,
        'INBOX': 1,
    },
    # 关键词权重
    'keywords': {
        'urgent': 8,
        '紧急': 8,
        'asap': 7,
        'important': 6,
        '重要': 6,
        'deadline': 5,
        '截止': 5,
        'action required': 6,
        '需要行动': 6,
        'please review': 4,
        '请审阅': 4,
    },
    # 发件人域名权重（示例）
    'sender_domains': {
        # 可以根据实际情况配置
        # 'important-client.com': 8,
        # 'boss-company.com': 10,
    }
}


class SkillImportanceHeuristics:
    """
    重要性评分技能

    基于规则为邮件/线程打分
    """

    def __init__(self, rules: Dict = None):
        """
        初始化

        Args:
            rules: 自定义规则，如果为 None 则使用默认规则
        """
        self.rules = rules or DEFAULT_RULES
        logger.debug(f"重要性评分规则已加载")

    def score_email(self, email: NormalizedEmail) -> float:
        """
        为单封邮件打分

        Args:
            email: 归一化的邮件

        Returns:
            重要性分数（0-100）
        """
        score = 0.0

        # 标签评分
        for label in email.labels:
            label_upper = label.upper()
            if label_upper in self.rules['labels']:
                score += self.rules['labels'][label_upper]

        # 关键词评分（在主题和正文中）
        text = f"{email.subject or ''} {email.body_plain}".lower()
        for keyword, weight in self.rules['keywords'].items():
            if keyword.lower() in text:
                score += weight

        # 发件人域名评分
        if email.from_addr:
            domain = self._extract_domain(email.from_addr)
            if domain in self.rules.get('sender_domains', {}):
                score += self.rules['sender_domains'][domain]

        # 限制在 0-100 范围内
        return min(score, 100.0)

    def score_thread(self, thread: ThreadContext) -> float:
        """
        为线程打分

        Args:
            thread: 线程上下文

        Returns:
            重要性分数（0-100）
        """
        if not thread.messages:
            return 0.0

        # 计算线程中所有邮件的平均分
        scores = [self.score_email(email) for email in thread.messages]
        avg_score = sum(scores) / len(scores)

        # 线程长度加成（邮件越多可能越重要）
        thread_bonus = min(len(thread.messages) * 0.5, 5.0)

        total_score = avg_score + thread_bonus

        return min(total_score, 100.0)

    def prioritize_threads(
        self,
        threads: List[ThreadContext]
    ) -> List[tuple[ThreadContext, float]]:
        """
        为线程列表排序并打分

        Args:
            threads: 线程列表

        Returns:
            (线程, 分数) 元组列表，按分数降序排序
        """
        scored_threads = []
        for thread in threads:
            score = self.score_thread(thread)
            scored_threads.append((thread, score))

        # 按分数降序排序
        scored_threads.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"已为 {len(threads)} 个线程评分并排序")
        return scored_threads

    @staticmethod
    def _extract_domain(email_addr: str) -> str:
        """
        从邮箱地址提取域名

        Args:
            email_addr: 邮箱地址

        Returns:
            域名
        """
        if '@' in email_addr:
            return email_addr.split('@')[-1].lower()
        return ""

    def get_priority_label(self, score: float) -> str:
        """
        根据分数返回优先级标签

        Args:
            score: 重要性分数

        Returns:
            优先级标签
        """
        if score >= 20:
            return "高"
        elif score >= 10:
            return "中"
        else:
            return "低"
