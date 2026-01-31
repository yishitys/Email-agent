"""
报告读取路由

从 SQLite 数据库读取已生成的报告与邮件引用。
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.db.report_store import SkillReportStore

logger = get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["报告"])


@router.get("/by-date/{report_date}")
async def get_report_by_date(report_date: date):
    """
    按日期获取报告（YYYY-MM-DD）
    """
    report = SkillReportStore.get_report_by_date(report_date)
    if not report:
        raise HTTPException(status_code=404, detail=f"未找到 {report_date} 的报告")
    return report


@router.get("/by-id/{report_id}")
async def get_report_by_id(report_id: int):
    """
    按 ID 获取报告
    """
    report = SkillReportStore.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"未找到 report_id={report_id} 的报告")
    return report


@router.get("")
async def list_reports(
    days: int = Query(30, ge=1, le=365, description="列出最近 N 天（最多 365）"),
):
    """
    列出最近 N 天的报告（按日期降序）
    """
    today = date.today()
    date_from = today.fromordinal(today.toordinal() - (days - 1))
    reports = SkillReportStore.list_reports(date_from=date_from, date_to=today)
    return {
        "date_from": date_from.isoformat(),
        "date_to": today.isoformat(),
        "count": len(reports),
        "reports": reports,
    }

