#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邮件报告查看器

使用方法:
    python view_report.py                 # 查看今天的报告
    python view_report.py 2026-01-29      # 查看指定日期的报告
    python view_report.py --list          # 列出所有报告
    python view_report.py --export        # 导出今天的报告为 Markdown 文件
"""
import sys
import os
from datetime import date, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.db.report_store import SkillReportStore


def print_separator(char='=', length=80):
    """打印分隔线"""
    print(char * length)


def print_report(report, report_date):
    """打印单个报告"""
    print_separator('=')
    print(f"📧 邮件报告 - {report_date.strftime('%Y年%m月%d日')}")
    print_separator('=')
    print()

    summary = report['summary']

    # 显示报告内容
    if summary.get('format') == 'markdown':
        # 新格式：Markdown
        print(summary['full_content'])
    else:
        # 旧格式：JSON
        print("## 📌 今日重点\n")
        highlights = summary.get('highlights', [])
        if highlights:
            for i, item in enumerate(highlights, 1):
                print(f"  {i}. {item}")
        else:
            print("  (无)")

        print("\n## ✅ 待办事项\n")
        todos = summary.get('todos', [])
        if todos:
            for i, item in enumerate(todos, 1):
                print(f"  {i}. {item}")
        else:
            print("  (无)")

        # 显示分类（如果有）
        categories = summary.get('categories', {})
        if any(categories.values()):
            print("\n## 📂 邮件分类\n")

            category_names = {
                'action_required': '需要行动',
                'important': '重要通知',
                'billing': '账单订阅',
                'social': '社交',
                'other': '其他'
            }

            for key, name in category_names.items():
                items = categories.get(key, [])
                if items:
                    print(f"\n### {name} ({len(items)})")
                    for item in items[:3]:  # 只显示前 3 个
                        if isinstance(item, dict):
                            print(f"  • {item.get('thread_subject', 'N/A')}")
                        else:
                            print(f"  • {item}")

    print()
    print_separator('-')

    # 显示统计信息
    email_count = report.get('email_count', 0)
    thread_count = report.get('thread_count', 0)
    ref_count = report.get('reference_count', 0)

    print(f"📊 统计: {email_count} 封邮件 | {thread_count} 个线程 | {ref_count} 个引用")
    print_separator('=')
    print()


def list_reports():
    """列出最近的所有报告"""
    print_separator('=')
    print("📋 报告列表（最近 30 天）")
    print_separator('=')
    print()

    found_reports = []

    # 查找最近 30 天的报告
    for i in range(30):
        check_date = date.today() - timedelta(days=i)
        report = SkillReportStore.get_report_by_date(check_date)

        if report:
            found_reports.append((check_date, report))

    if not found_reports:
        print("❌ 未找到任何报告")
        print()
        print("提示: 运行以下命令生成报告:")
        print("  python scripts/generate_daily_report.py --hours 24")
        return

    print(f"找到 {len(found_reports)} 份报告:\n")

    for report_date, report in found_reports:
        email_count = report.get('email_count', 0)
        thread_count = report.get('thread_count', 0)
        summary = report['summary']
        report_format = summary.get('format', 'JSON')

        # 获取第一条 highlight 作为预览
        preview = ""
        if summary.get('format') == 'markdown':
            content = summary.get('full_content', '')
            # 提取第一行非空内容
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            if lines:
                preview = lines[0][:60]
                if len(lines[0]) > 60:
                    preview += "..."
        else:
            highlights = summary.get('highlights', [])
            if highlights:
                preview = highlights[0][:60]
                if len(highlights[0]) > 60:
                    preview += "..."

        print(f"  📅 {report_date} [{report_format}]")
        print(f"     {email_count} 邮件, {thread_count} 线程")
        if preview:
            print(f"     {preview}")
        print()

    print_separator('=')
    print()


def export_report(report_date):
    """导出报告为 Markdown 文件"""
    report = SkillReportStore.get_report_by_date(report_date)

    if not report:
        print(f"❌ 未找到 {report_date} 的报告")
        return

    # 创建导出目录
    export_dir = Path('data/exports')
    export_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    filename = f"email_report_{report_date}.md"
    filepath = export_dir / filename

    summary = report['summary']

    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# 📧 邮件报告 - {report_date.strftime('%Y年%m月%d日')}\n\n")
        # “同一天重复生成报告”会更新 summary/引用，但 created_at 仍是首次创建时间。
        # 导出时用 updated_at（最后生成/更新时间）更符合预期。
        generated_at = report.get('updated_at') or report.get('created_at') or 'N/A'
        f.write(f"生成时间: {generated_at}\n\n")
        f.write("---\n\n")

        if summary.get('format') == 'markdown':
            f.write(summary['full_content'])
        else:
            f.write("## 📌 今日重点\n\n")
            for item in summary.get('highlights', []):
                f.write(f"- {item}\n")

            f.write("\n## ✅ 待办事项\n\n")
            for item in summary.get('todos', []):
                f.write(f"- [ ] {item}\n")

            # 分类
            categories = summary.get('categories', {})
            if any(categories.values()):
                f.write("\n## 📂 邮件分类\n\n")

                category_names = {
                    'action_required': '需要行动',
                    'important': '重要通知',
                    'billing': '账单订阅',
                    'social': '社交',
                    'other': '其他'
                }

                for key, name in category_names.items():
                    items = categories.get(key, [])
                    if items:
                        f.write(f"\n### {name}\n\n")
                        for item in items:
                            if isinstance(item, dict):
                                f.write(f"- **{item.get('thread_subject', 'N/A')}**\n")
                                f.write(f"  - {item.get('summary', '')}\n")
                                if item.get('action'):
                                    f.write(f"  - 建议: {item.get('action')}\n")
                            else:
                                f.write(f"- {item}\n")

        f.write("\n\n---\n\n")
        f.write(f"📊 统计: {report.get('email_count', 0)} 封邮件, ")
        f.write(f"{report.get('thread_count', 0)} 个线程\n")

    print(f"✅ 报告已导出到: {filepath}")
    print()


def main():
    """主函数"""
    # 解析参数
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ['--list', '-l']:
            # 列出所有报告
            list_reports()
            return

        elif arg in ['--export', '-e']:
            # 导出报告
            if len(sys.argv) > 2:
                try:
                    report_date = date.fromisoformat(sys.argv[2])
                except ValueError:
                    print(f"❌ 无效的日期格式: {sys.argv[2]}")
                    print("请使用 YYYY-MM-DD 格式，例如: 2026-01-29")
                    return
            else:
                report_date = date.today()

            export_report(report_date)
            return

        elif arg in ['--help', '-h']:
            # 显示帮助
            print(__doc__)
            return

        else:
            # 尝试解析为日期
            try:
                report_date = date.fromisoformat(arg)
            except ValueError:
                print(f"❌ 无效的日期格式: {arg}")
                print("请使用 YYYY-MM-DD 格式，例如: 2026-01-29")
                print()
                print("或使用以下选项:")
                print("  --list    列出所有报告")
                print("  --export  导出报告为 Markdown 文件")
                print("  --help    显示帮助")
                return
    else:
        # 默认查看今天的报告
        report_date = date.today()

    # 获取报告
    report = SkillReportStore.get_report_by_date(report_date)

    if report:
        print_report(report, report_date)
    else:
        print()
        print(f"❌ 未找到 {report_date.strftime('%Y年%m月%d日')} 的报告")
        print()
        print("提示:")
        print("  1. 运行以下命令生成报告:")
        print("     python scripts/generate_daily_report.py --hours 24")
        print()
        print("  2. 查看其他日期的报告:")
        print("     python view_report.py 2026-01-29")
        print()
        print("  3. 列出所有报告:")
        print("     python view_report.py --list")
        print()


if __name__ == '__main__':
    main()
