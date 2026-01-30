"""
测试存储层功能
"""
import sys
from datetime import date, datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.report_store import SkillReportStore, ReportData
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_report_store():
    """测试报告存储功能"""
    print("=" * 60)
    print("存储层测试")
    print("=" * 60)
    print()

    # 创建内存数据库（用于测试）
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 测试 1: 保存报告
        print("测试 1: 保存报告")
        print("-" * 60)

        report_data = ReportData(
            date=date(2026, 1, 30),
            summary={
                "highlights": ["重要邮件1", "重要邮件2", "重要邮件3"],
                "todos": ["回复客户A", "准备会议资料"],
                "categories": {
                    "action_required": 3,
                    "important": 5,
                    "social": 2
                }
            },
            email_refs=[
                {
                    "message_id": "msg_001",
                    "thread_id": "thread_001",
                    "subject": "测试邮件 1",
                    "from_addr": "sender1@example.com",
                    "to_addr": "me@example.com",
                    "date": datetime(2026, 1, 30, 10, 0, 0),
                    "snippet": "这是第一封测试邮件的摘要...",
                    "gmail_url": "https://mail.google.com/mail/u/0/#inbox/msg_001"
                },
                {
                    "message_id": "msg_002",
                    "thread_id": "thread_001",
                    "subject": "Re: 测试邮件 1",
                    "from_addr": "sender2@example.com",
                    "to_addr": "me@example.com",
                    "date": datetime(2026, 1, 30, 11, 30, 0),
                    "snippet": "这是对第一封邮件的回复...",
                    "gmail_url": "https://mail.google.com/mail/u/0/#inbox/msg_002"
                },
            ]
        )

        report_id = SkillReportStore.save_report(report_data, db)
        print(f"✓ 报告保存成功: report_id={report_id}")
        print()

        # 测试 2: 根据 ID 获取报告
        print("测试 2: 根据 ID 获取报告")
        print("-" * 60)

        report = SkillReportStore.get_report_by_id(report_id, db)
        if report:
            print(f"✓ 获取报告成功:")
            print(f"  ID: {report['id']}")
            print(f"  日期: {report['date']}")
            print(f"  摘要: {report['summary']}")
            print(f"  邮件引用数量: {len(report['email_references'])}")
            for i, ref in enumerate(report['email_references'], 1):
                print(f"    邮件 {i}: {ref['subject']} (from: {ref['from_addr']})")
        else:
            print("✗ 获取报告失败")
        print()

        # 测试 3: 根据日期获取报告
        print("测试 3: 根据日期获取报告")
        print("-" * 60)

        report = SkillReportStore.get_report_by_date(date(2026, 1, 30), db)
        if report:
            print(f"✓ 根据日期获取报告成功: {report['date']}")
        else:
            print("✗ 根据日期获取报告失败")
        print()

        # 测试 4: 列出所有报告
        print("测试 4: 列出所有报告")
        print("-" * 60)

        # 先添加更多报告
        for day in range(28, 30):
            extra_report = ReportData(
                date=date(2026, 1, day),
                summary={"highlights": [f"{day}日的重点"]},
                email_refs=[]
            )
            SkillReportStore.save_report(extra_report, db)

        reports = SkillReportStore.list_reports(db=db)
        print(f"✓ 列出报告成功，共 {len(reports)} 条:")
        for report in reports:
            print(f"  - {report['date']}: {len(report['email_references'])} 封邮件引用")
        print()

        # 测试 5: 按日期范围查询
        print("测试 5: 按日期范围查询")
        print("-" * 60)

        reports = SkillReportStore.list_reports(
            date_from=date(2026, 1, 29),
            date_to=date(2026, 1, 30),
            db=db
        )
        print(f"✓ 日期范围查询成功，共 {len(reports)} 条:")
        for report in reports:
            print(f"  - {report['date']}")
        print()

        # 测试 6: 更新已存在的报告
        print("测试 6: 更新已存在的报告")
        print("-" * 60)

        updated_report = ReportData(
            date=date(2026, 1, 30),
            summary={
                "highlights": ["更新后的重点1", "更新后的重点2"],
                "todos": ["新的待办事项"],
            },
            email_refs=[
                {
                    "message_id": "msg_003",
                    "thread_id": "thread_002",
                    "subject": "更新后的邮件",
                    "from_addr": "new@example.com",
                    "snippet": "这是更新后的邮件",
                }
            ]
        )

        report_id_2 = SkillReportStore.save_report(updated_report, db)
        print(f"✓ 报告更新成功: report_id={report_id_2}")

        # 验证是否是同一个 ID（更新而非新建）
        if report_id == report_id_2:
            print("✓ 确认是更新操作（ID 相同）")
        else:
            print("✗ ID 不同，可能是新建而非更新")

        # 验证邮件引用是否已更新
        updated = SkillReportStore.get_report_by_id(report_id_2, db)
        print(f"  更新后的邮件引用数量: {len(updated['email_references'])}")
        print()

        # 测试 7: 删除报告
        print("测试 7: 删除报告")
        print("-" * 60)

        success = SkillReportStore.delete_report(report_id, db)
        if success:
            print(f"✓ 报告删除成功: report_id={report_id}")

            # 验证删除
            deleted_report = SkillReportStore.get_report_by_id(report_id, db)
            if deleted_report is None:
                print("✓ 确认报告已删除")
            else:
                print("✗ 报告仍然存在")
        else:
            print("✗ 报告删除失败")
        print()

        print("=" * 60)
        print("所有测试完成！")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    test_report_store()
