"""
生成邮件报告 - 命令行工具

用法:
    python scripts/generate_report.py                    # 生成今天的报告
    python scripts/generate_report.py --date 2026-01-30  # 生成指定日期的报告
    python scripts/generate_report.py --hours 24         # 生成最近 24 小时的报告
"""
import sys
import argparse
from pathlib import Path
from datetime import date, datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.report_pipeline import ReportPipeline, ReportPipelineError
from app.integrations.gmail.auth import AuthError
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='生成邮件报告',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 生成今天的报告
  python scripts/generate_report.py

  # 生成指定日期的报告
  python scripts/generate_report.py --date 2026-01-30

  # 生成最近 24 小时的报告
  python scripts/generate_report.py --hours 24
        """
    )

    parser.add_argument(
        '--date',
        type=str,
        help='报告日期 (YYYY-MM-DD)，默认为今天'
    )

    parser.add_argument(
        '--hours',
        type=int,
        help='拉取最近 N 小时的邮件（如果指定，则忽略 --date）'
    )

    args = parser.parse_args()

    # 确定报告日期
    if args.date:
        try:
            report_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"错误: 日期格式不正确，应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        report_date = date.today()

    # 显示任务信息
    print()
    print("=" * 60)
    print("邮件报告生成工具")
    print("=" * 60)
    print()

    if args.hours:
        print(f"任务: 生成最近 {args.hours} 小时的邮件报告")
        print(f"报告日期: {report_date}")
    else:
        print(f"任务: 生成 {report_date} 的邮件报告")

    print()

    try:
        # 生成报告
        result = ReportPipeline.generate_report_for_date(
            report_date=report_date,
            last_n_hours=args.hours
        )

        # 显示结果
        print()
        print("=" * 60)
        print("报告生成成功！")
        print("=" * 60)
        print()
        print(f"报告 ID: {result['report_id']}")
        print(f"报告日期: {result['date']}")
        print(f"邮件数量: {result['email_count']}")
        print(f"线程数量: {result['thread_count']}")
        print(f"引用数量: {result['reference_count']}")
        print()

        # 显示摘要预览
        summary = result['summary']
        if summary.get('highlights'):
            print("今日重点:")
            for i, highlight in enumerate(summary['highlights'][:5], 1):
                print(f"  {i}. {highlight}")
            print()

        if summary.get('todos'):
            print("待办事项:")
            for i, todo in enumerate(summary['todos'][:5], 1):
                print(f"  {i}. {todo}")
            print()

        print("=" * 60)
        print(f"报告已保存到数据库，ID: {result['report_id']}")
        print("=" * 60)
        print()

        sys.exit(0)

    except AuthError as e:
        print()
        print("=" * 60)
        print("认证错误")
        print("=" * 60)
        print()
        print(f"错误: {e}")
        print()

        if e.needs_reauth:
            print("请执行以下步骤重新授权:")
            print("  1. 启动 Web 服务器:")
            print("     uvicorn app.main:app --host 127.0.0.1 --port 8000")
            print()
            print("  2. 在浏览器中访问:")
            print("     http://127.0.0.1:8000/auth/google")
            print()
            print("  3. 完成授权后，再次运行此脚本")
            print()

        sys.exit(1)

    except ReportPipelineError as e:
        print()
        print("=" * 60)
        print("报告生成失败")
        print("=" * 60)
        print()
        print(f"错误: {e}")
        print()
        print("请检查:")
        print("  1. OpenAI API key 是否正确配置 (.env)")
        print("  2. 网络连接是否正常")
        print("  3. Gmail 凭据是否有效")
        print()
        sys.exit(1)

    except KeyboardInterrupt:
        print()
        print("用户中断")
        sys.exit(130)

    except Exception as e:
        print()
        print("=" * 60)
        print("未知错误")
        print("=" * 60)
        print()
        print(f"错误: {e}")
        print()
        logger.error("报告生成失败", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
