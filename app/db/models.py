"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Date
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Report(Base):
    """
    邮件报告模型

    存储每日生成的邮件报告
    """
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True, unique=True, comment="报告日期")
    summary_json = Column(Text, nullable=False, comment="报告摘要 JSON（分类、待办、重点等）")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联的邮件引用
    email_references = relationship("EmailReference", back_populates="report", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Report(id={self.id}, date={self.date}, created_at={self.created_at})>"


class EmailReference(Base):
    """
    邮件引用模型

    存储报告中引用的邮件元数据（不存储完整正文）
    """
    __tablename__ = "email_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False, index=True, comment="关联的报告 ID")

    # Gmail 邮件标识
    message_id = Column(String(255), nullable=False, index=True, comment="Gmail message ID")
    thread_id = Column(String(255), nullable=True, index=True, comment="Gmail thread ID")

    # 邮件元数据
    subject = Column(String(500), nullable=True, comment="邮件主题")
    from_addr = Column(String(255), nullable=True, comment="发件人地址")
    to_addr = Column(String(255), nullable=True, comment="收件人地址")
    date = Column(DateTime, nullable=True, comment="邮件日期")

    # 邮件摘要
    snippet = Column(Text, nullable=True, comment="邮件片段/摘要")

    # Gmail 链接
    gmail_url = Column(String(500), nullable=True, comment="Gmail 网页链接")

    # 关联的报告
    report = relationship("Report", back_populates="email_references")

    def __repr__(self):
        return f"<EmailReference(id={self.id}, message_id={self.message_id}, subject={self.subject[:30]})>"
