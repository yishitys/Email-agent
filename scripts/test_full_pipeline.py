"""
测试完整的报告生成管线（使用模拟数据）
"""
import sys
from pathlib import Path
from datetime import date, datetime
from unittest.mock import Mock, patch

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.report_pipeline import ReportPipeline
from app.integrations.gmail.fetch import MessageSummary
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_pipeline_with_mock_data():
    """使用模拟数据测试完整管线"""
    print()
    print("=" * 60)
    print("完整管线测试（模拟数据）")
    print("=" * 60)
    print()

    # 创建模拟邮件数据
    mock_messages = [
        MessageSummary(
            id="msg_001",
            thread_id="thread_001",
            subject="紧急：项目截止日期提醒",
            from_addr="Boss <boss@company.com>",
            to_addr="me@company.com",
            date=datetime(2026, 1, 30, 9, 0, 0),
            snippet="项目需要在本周五前完成，请确认进度并提交最终报告...",
            labels=["IMPORTANT", "UNREAD", "INBOX"]
        ),
        MessageSummary(
            id="msg_002",
            thread_id="thread_002",
            subject="会议邀请：下周团队讨论",
            from_addr="Manager <manager@company.com>",
            to_addr="me@company.com",
            date=datetime(2026, 1, 30, 10, 30, 0),
            snippet="下周二上午10点，会议室A，讨论Q1规划...",
            labels=["INBOX"]
        ),
        MessageSummary(
            id="msg_003",
            thread_id="thread_003",
            subject="AWS 账单: 2026年1月",
            from_addr="AWS <billing@aws.com>",
            to_addr="me@company.com",
            date=datetime(2026, 1, 30, 8, 0, 0),
            snippet="您的1月份使用费用为 $1,234.56...",
            labels=["INBOX"]
        ),
    ]

    # 模拟 GPT 响应
    mock_gpt_response = {
        'highlights': [
            '紧急项目本周五截止，需要确认进度',
            '下周二团队会议讨论Q1规划',
            'AWS 1月账单 $1,234.56'
        ],
        'todos': [
            '完成项目报告并提交',
            '确认下周二会议时间',
            '审核 AWS 账单明细'
        ],
        'categories': {
            'action_required': [
                {
                    'thread_subject': '紧急：项目截止日期提醒',
                    'summary': '项目本周五截止，需要提交最终报告',
                    'action': '确认项目完成度并准备报告'
                }
            ],
            'important': [
                {
                    'thread_subject': '会议邀请：下周团队讨论',
                    'summary': '下周二上午10点讨论Q1规划',
                    'action': '查看议程并准备材料'
                }
            ],
            'billing': [
                {
                    'thread_subject': 'AWS 账单: 2026年1月',
                    'summary': '1月份 AWS 使用费用 $1,234.56',
                    'action': '审核账单详情'
                }
            ],
            'social': [],
            'other': []
        }
    }

    print("准备测试数据:")
    print(f"  - 模拟邮件: {len(mock_messages)} 封")
    print(f"  - 模拟 GPT 响应: 已准备")
    print()

    # Mock 相关服务
    with patch('app.services.report_pipeline.SkillGmailAuth.load_credentials') as mock_auth, \
         patch('app.services.report_pipeline.SkillGmailFetch.fetch_messages') as mock_fetch, \
         patch('app.services.report_pipeline.SkillGptSummarize') as MockGptSummarize:

        # 配置 mock
        mock_creds = Mock()
        mock_auth.return_value = mock_creds
        mock_fetch.return_value = mock_messages

        mock_gpt = Mock()
        mock_gpt.summarize.return_value = mock_gpt_response
        mock_gpt.validate_report.return_value = True
        MockGptSummarize.return_value = mock_gpt

        # 执行管线
        try:
            result = ReportPipeline.generate_report_for_date(
                report_date=date(2026, 1, 30)
            )

            # 显示结果
            print()
            print("=" * 60)
            print("测试成功！")
            print("=" * 60)
            print()
            print("生成的报告:")
            print(f"  报告 ID: {result['report_id']}")
            print(f"  日期: {result['date']}")
            print(f"  邮件数: {result['email_count']}")
            print(f"  线程数: {result['thread_count']}")
            print(f"  引用数: {result['reference_count']}")
            print()

            summary = result['summary']
            print("今日重点:")
            for i, highlight in enumerate(summary['highlights'], 1):
                print(f"  {i}. {highlight}")
            print()

            print("待办事项:")
            for i, todo in enumerate(summary['todos'], 1):
                print(f"  {i}. {todo}")
            print()

            # 显示分类
            print("邮件分类:")
            for category, items in summary['categories'].items():
                if items:
                    print(f"  [{category}]: {len(items)} 个")
            print()

            print("=" * 60)
            print("管线测试完成！所有步骤都成功执行")
            print("=" * 60)
            print()

            # 验证数据库
            print("验证数据库保存...")
            from app.db.report_store import SkillReportStore
            saved_report = SkillReportStore.get_report_by_id(result['report_id'])

            if saved_report:
                print(f"✓ 报告已保存到数据库")
                print(f"  - ID: {saved_report['id']}")
                print(f"  - 日期: {saved_report['date']}")
                print(f"  - 邮件引用: {len(saved_report['email_references'])} 个")
            else:
                print("✗ 数据库验证失败")

            print()

            return True

        except Exception as e:
            print()
            print("=" * 60)
            print("测试失败")
            print("=" * 60)
            print()
            print(f"错误: {e}")
            logger.error("测试失败", exc_info=True)
            return False


if __name__ == "__main__":
    success = test_pipeline_with_mock_data()
    sys.exit(0 if success else 1)
