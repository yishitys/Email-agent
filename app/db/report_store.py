"""
SkillReportStore - 报告存储服务

提供报告和邮件引用的持久化操作
"""
import json
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Report, EmailReference
from app.db.session import get_db

logger = get_logger(__name__)


class ReportData:
    """报告数据类（用于传递数据，不直接使用 ORM 模型）"""

    def __init__(
        self,
        date: date,
        summary: Dict[str, Any],
        email_refs: Optional[List[Dict[str, Any]]] = None
    ):
        """
        初始化报告数据

        Args:
            date: 报告日期
            summary: 报告摘要（字典格式，将被序列化为 JSON）
            email_refs: 邮件引用列表
        """
        self.date = date
        self.summary = summary
        self.email_refs = email_refs or []


class SkillReportStore:
    """
    报告存储技能

    提供报告的增删改查功能
    """

    @staticmethod
    def save_report(
        report_data: ReportData,
        db: Optional[Session] = None
    ) -> int:
        """
        保存报告及其邮件引用

        Args:
            report_data: 报告数据
            db: 数据库会话（可选，如果不提供则自动创建）

        Returns:
            保存的报告 ID

        Raises:
            ValueError: 如果同一日期的报告已存在
            Exception: 数据库操作失败
        """
        def _save(session: Session) -> int:
            # 检查是否已存在同日期的报告
            existing = session.query(Report).filter(
                Report.date == report_data.date
            ).first()

            if existing:
                logger.warning(f"日期 {report_data.date} 的报告已存在，将更新")
                # 更新现有报告
                existing.summary_json = json.dumps(report_data.summary, ensure_ascii=False)
                existing.updated_at = datetime.utcnow()

                # 删除旧的邮件引用
                session.query(EmailReference).filter(
                    EmailReference.report_id == existing.id
                ).delete()

                report_id = existing.id
            else:
                # 创建新报告
                report = Report(
                    date=report_data.date,
                    summary_json=json.dumps(report_data.summary, ensure_ascii=False),
                )
                session.add(report)
                session.flush()  # 获取 report.id
                report_id = report.id

            # 添加邮件引用
            if report_data.email_refs:
                for ref_data in report_data.email_refs:
                    email_ref = EmailReference(
                        report_id=report_id,
                        message_id=ref_data.get("message_id"),
                        thread_id=ref_data.get("thread_id"),
                        subject=ref_data.get("subject"),
                        from_addr=ref_data.get("from_addr"),
                        to_addr=ref_data.get("to_addr"),
                        date=ref_data.get("date"),
                        snippet=ref_data.get("snippet"),
                        gmail_url=ref_data.get("gmail_url"),
                    )
                    session.add(email_ref)

            session.commit()
            logger.info(f"报告保存成功: report_id={report_id}, date={report_data.date}")
            return report_id

        if db:
            return _save(db)
        else:
            with get_db() as session:
                return _save(session)

    @staticmethod
    def get_report_by_id(
        report_id: int,
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取报告

        Args:
            report_id: 报告 ID
            db: 数据库会话（可选）

        Returns:
            报告字典，包含 summary 和 email_references；如果不存在返回 None
        """
        def _get(session: Session) -> Optional[Dict[str, Any]]:
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                logger.warning(f"报告不存在: report_id={report_id}")
                return None

            return SkillReportStore._report_to_dict(report)

        if db:
            return _get(db)
        else:
            with get_db() as session:
                return _get(session)

    @staticmethod
    def get_report_by_date(
        report_date: date,
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        根据日期获取报告

        Args:
            report_date: 报告日期
            db: 数据库会话（可选）

        Returns:
            报告字典；如果不存在返回 None
        """
        def _get(session: Session) -> Optional[Dict[str, Any]]:
            # 理论上 reports.date 应该是唯一的；但为了兼容历史数据库/异常数据，
            # 这里始终按更新时间倒序取“最新”的那一条。
            report = (
                session.query(Report)
                .filter(Report.date == report_date)
                .order_by(Report.updated_at.desc(), Report.id.desc())
                .first()
            )
            if not report:
                logger.info(f"日期 {report_date} 没有报告")
                return None

            return SkillReportStore._report_to_dict(report)

        if db:
            return _get(db)
        else:
            with get_db() as session:
                return _get(session)

    @staticmethod
    def list_reports(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        列出报告（支持日期范围过滤）

        Args:
            date_from: 起始日期（包含），None 表示不限制
            date_to: 结束日期（包含），None 表示不限制
            db: 数据库会话（可选）

        Returns:
            报告列表（按日期降序）
        """
        def _list(session: Session) -> List[Dict[str, Any]]:
            query = session.query(Report)

            # 应用日期过滤
            if date_from and date_to:
                query = query.filter(and_(
                    Report.date >= date_from,
                    Report.date <= date_to
                ))
            elif date_from:
                query = query.filter(Report.date >= date_from)
            elif date_to:
                query = query.filter(Report.date <= date_to)

            # 按日期降序排序
            reports = query.order_by(Report.date.desc()).all()

            logger.info(f"查询到 {len(reports)} 条报告")
            return [SkillReportStore._report_to_dict(r) for r in reports]

        if db:
            return _list(db)
        else:
            with get_db() as session:
                return _list(session)

    @staticmethod
    def delete_report(
        report_id: int,
        db: Optional[Session] = None
    ) -> bool:
        """
        删除报告（及其关联的邮件引用）

        Args:
            report_id: 报告 ID
            db: 数据库会话（可选）

        Returns:
            是否删除成功
        """
        def _delete(session: Session) -> bool:
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                logger.warning(f"报告不存在，无法删除: report_id={report_id}")
                return False

            session.delete(report)
            session.commit()
            logger.info(f"报告已删除: report_id={report_id}")
            return True

        if db:
            return _delete(db)
        else:
            with get_db() as session:
                return _delete(session)

    @staticmethod
    def _report_to_dict(report: Report) -> Dict[str, Any]:
        """
        将 Report ORM 对象转换为字典

        Args:
            report: Report 对象

        Returns:
            报告字典
        """
        refs = list(report.email_references)
        ref_count = len(refs)
        thread_count = len(set(ref.thread_id for ref in refs if ref.thread_id))

        return {
            "id": report.id,
            "date": report.date.isoformat(),
            "summary": json.loads(report.summary_json),
            "created_at": report.created_at.isoformat(),
            "updated_at": report.updated_at.isoformat(),
            "email_references": [
                {
                    "id": ref.id,
                    "message_id": ref.message_id,
                    "thread_id": ref.thread_id,
                    "subject": ref.subject,
                    "from_addr": ref.from_addr,
                    "to_addr": ref.to_addr,
                    "date": ref.date.isoformat() if ref.date else None,
                    "snippet": ref.snippet,
                    "gmail_url": ref.gmail_url,
                }
                for ref in refs
            ],
            "email_count": ref_count,
            "thread_count": thread_count,
            "reference_count": ref_count,
        }
