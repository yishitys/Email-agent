"""
报告生成管线

串联所有模块，生成完整的邮件报告
"""
import re
from datetime import date, timedelta
from typing import Optional, Dict, Any

from google.oauth2.credentials import Credentials

from app.core.logging import get_logger
from app.integrations.gmail.auth import SkillGmailAuth, AuthError
from app.integrations.gmail.fetch import SkillGmailFetch
from app.integrations.gmail.normalize import SkillEmailNormalize
from app.services.thread_merge import SkillThreadMerge
from app.services.importance import SkillImportanceHeuristics
from app.integrations.openai.prompts import SkillPromptCompose
from app.integrations.openai.summarize import SkillGptSummarize, GptError
from app.integrations.anthropic.summarize import SkillClaudeSummarize, ClaudeError
from app.core.config import config as app_config
from app.db.report_store import SkillReportStore, ReportData

logger = get_logger(__name__)


class ReportPipelineError(Exception):
    """报告生成管线错误"""
    pass


class ReportPipeline:
    """
    报告生成管线

    完整的报告生成流程
    """

    @staticmethod
    def generate_report_for_date(
        report_date: date,
        credentials: Optional[Credentials] = None,
        last_n_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        生成指定日期的邮件报告

        Args:
            report_date: 报告日期
            credentials: Google 凭据，如果为 None 则自动加载
            last_n_hours: 拉取最近 N 小时的邮件，如果指定则忽略 date 范围

        Returns:
            生成的报告字典，包含 report_id 和 summary

        Raises:
            AuthError: 认证失败
            ReportPipelineError: 管线执行失败
        """
        logger.info("=" * 60)
        logger.info(f"开始生成报告: {report_date}")
        logger.info("=" * 60)

        try:
            # Step 1: 加载凭据
            logger.info("步骤 1/7: 加载 Gmail 凭据")
            if credentials is None:
                credentials = SkillGmailAuth.load_credentials()
                if credentials is None:
                    raise AuthError("未找到有效凭据，请先进行授权", needs_reauth=True)
            logger.info("✓ 凭据加载成功")

            # Step 2: 拉取邮件
            logger.info("步骤 2/7: 拉取邮件")
            if last_n_hours:
                # 最近 N 小时
                messages = SkillGmailFetch.fetch_messages(
                    credentials=credentials,
                    last_n_hours=last_n_hours,
                    max_results=100
                )
                logger.info(f"✓ 拉取了最近 {last_n_hours} 小时的 {len(messages)} 封邮件")
            else:
                # 指定日期（当天 00:00 到 23:59）
                messages = SkillGmailFetch.fetch_messages(
                    credentials=credentials,
                    date_from=report_date,
                    date_to=report_date,
                    max_results=100
                )
                logger.info(f"✓ 拉取了 {len(messages)} 封邮件")

            # 检查是否有邮件
            if not messages:
                logger.info("没有邮件，生成空报告")
                return ReportPipeline._generate_empty_report(report_date)

            # Step 3: 归一化邮件
            logger.info("步骤 3/7: 归一化邮件")
            normalized_emails = []
            for msg in messages:
                normalized = SkillEmailNormalize.normalize(msg)
                normalized_emails.append(normalized)
            logger.info(f"✓ 归一化了 {len(normalized_emails)} 封邮件")

            # Step 4: 合并线程
            logger.info("步骤 4/7: 合并线程")
            threads = SkillThreadMerge.merge_threads(normalized_emails)
            logger.info(f"✓ 合并为 {len(threads)} 个线程")

            # Step 5: 重要性评分
            logger.info("步骤 5/7: 重要性评分")
            scorer = SkillImportanceHeuristics()
            scored_threads = scorer.prioritize_threads(threads)
            logger.info(f"✓ 完成评分，最高分: {scored_threads[0][1]:.1f}" if scored_threads else "✓ 完成评分")

            # Step 6: 生成 Prompt 并调用 AI
            ai_provider = app_config.AI_PROVIDER
            logger.info(f"步骤 6/7: 调用 {ai_provider.upper()} 生成报告")
            system_prompt, user_prompt = SkillPromptCompose.compose(
                scored_threads,
                report_date
            )

            try:
                # 根据配置选择 AI 提供商
                if ai_provider == "claude":
                    ai_client = SkillClaudeSummarize()
                    ai_response = ai_client.summarize(system_prompt, user_prompt)
                else:  # openai
                    ai_client = SkillGptSummarize()
                    ai_response = ai_client.summarize(system_prompt, user_prompt)

                # 根据格式解析响应
                if ai_response.get('format') == 'markdown':
                    summary = ReportPipeline._parse_markdown_report(ai_response['content'])
                else:
                    summary = ai_response  # 旧 JSON 格式

                # 验证报告结构
                if not ai_client.validate_report(ai_response):
                    logger.warning("AI 返回的报告结构不完整，使用默认结构")
                    summary = ReportPipeline._fix_report_structure(summary)

                logger.info(f"✓ {ai_provider.upper()} 报告生成成功")

            except (GptError, ClaudeError) as e:
                logger.error(f"AI 调用失败: {e}")
                # 生成降级报告（不使用 AI）
                summary = ReportPipeline._generate_fallback_summary(scored_threads)
                logger.info("✓ 使用降级报告（未调用 AI）")

            # Step 7: 保存报告
            logger.info("步骤 7/7: 保存报告到数据库")

            # 构建邮件引用
            email_refs = []
            for thread, score in scored_threads[:20]:  # 最多保存 20 个线程的引用
                for msg in thread.messages:
                    email_refs.append({
                        'message_id': msg.message_id,
                        'thread_id': msg.thread_id,
                        'subject': msg.subject,
                        'from_addr': msg.from_addr,
                        'to_addr': msg.to_addr,
                        'date': msg.date,
                        'snippet': msg.snippet,
                        'gmail_url': f"https://mail.google.com/mail/u/0/#inbox/{msg.message_id}"
                    })

            # 创建报告数据
            report_data = ReportData(
                date=report_date,
                summary=summary,
                email_refs=email_refs
            )

            # 保存
            report_id = SkillReportStore.save_report(report_data)
            logger.info(f"✓ 报告已保存，ID: {report_id}")

            logger.info("=" * 60)
            logger.info(f"报告生成完成！报告 ID: {report_id}")
            logger.info("=" * 60)

            return {
                'report_id': report_id,
                'date': report_date.isoformat(),
                'summary': summary,
                'email_count': len(messages),
                'thread_count': len(threads),
                'reference_count': len(email_refs)
            }

        except AuthError:
            # 重新抛出认证错误
            raise

        except Exception as e:
            logger.error(f"报告生成失败: {e}", exc_info=True)
            raise ReportPipelineError(f"报告生成失败: {e}") from e

    @staticmethod
    def _generate_empty_report(report_date: date) -> Dict[str, Any]:
        """
        生成空报告

        Args:
            report_date: 报告日期

        Returns:
            报告字典
        """
        summary = {
            'highlights': ['今日无新邮件'],
            'todos': [],
            'categories': {
                'action_required': [],
                'important': [],
                'billing': [],
                'social': [],
                'other': []
            }
        }

        report_data = ReportData(
            date=report_date,
            summary=summary,
            email_refs=[]
        )

        report_id = SkillReportStore.save_report(report_data)
        logger.info(f"✓ 空报告已保存，ID: {report_id}")

        return {
            'report_id': report_id,
            'date': report_date.isoformat(),
            'summary': summary,
            'email_count': 0,
            'thread_count': 0,
            'reference_count': 0
        }

    @staticmethod
    def _generate_fallback_summary(scored_threads) -> Dict[str, Any]:
        """
        生成降级摘要（不使用 AI）

        与 AI 报告格式一致：重要（score>=20）仅 3 字段，非重要仅发件人+一句话摘要。
        保留 ## ⚡ 今日重点 与 ## ✅ 行动清单 以兼容解析器。

        Args:
            scored_threads: 评分后的线程列表

        Returns:
            Markdown 格式的简单报告
        """
        # 按 score>=20 分为重要 / 非重要
        important = [(t, s) for t, s in scored_threads if s >= 20]
        non_important = [(t, s) for t, s in scored_threads if s < 20]

        total_emails = sum(t.total_messages for t, _ in scored_threads)
        report_parts = [
            "*此报告未使用 AI 生成*",
            ""
        ]

        # ## 📧 重要邮件：仅 发件人 / 时间 / 内容摘要
        report_parts.append("## 📧 重要邮件")
        report_parts.append("")
        if important:
            for thread, _ in important[:20]:
                sender_display = "未知发件人"
                time_str = "未知"
                snippet = ""
                if thread.messages:
                    msg = thread.messages[0]
                    sender_display = msg.sender_name or msg.from_addr or "未知"
                    time_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "未知"
                    snippet = (msg.snippet or "")[:200]
                    if len(msg.snippet or "") > 200:
                        snippet += "..."
                report_parts.append(f"**{thread.subject}**")
                report_parts.append(f"- **发件人**: {sender_display}")
                report_parts.append(f"- **时间**: {time_str}")
                report_parts.append(f"- **内容摘要**: {snippet or '（无摘要）'}")
                report_parts.append("")
        else:
            report_parts.append("（无）")
            report_parts.append("")

        # ## 📋 非重要邮件：发件人 + 一句话摘要
        report_parts.append("## 📋 非重要邮件")
        report_parts.append("")
        if non_important:
            for thread, _ in non_important[:30]:
                sender_display = "未知"
                one_line = ""
                if thread.messages:
                    msg = thread.messages[0]
                    sender_display = msg.sender_name or msg.from_addr or "未知"
                    one_line = (msg.snippet or thread.subject or "")[:80]
                    if len(msg.snippet or thread.subject or "") > 80:
                        one_line += "..."
                report_parts.append(f"**{thread.subject}** — **发件人**: {sender_display}。{one_line}")
            report_parts.append("")
        else:
            report_parts.append("（无）")
            report_parts.append("")

        # ## ⚡ 今日重点
        report_parts.append("## ⚡ 今日重点")
        report_parts.append("")
        report_parts.append(f"- 共收到 {len(scored_threads)} 个邮件线程，{total_emails} 封邮件")
        if important:
            report_parts.append("- 请优先查看「重要邮件」章节")
        report_parts.append("")

        # ## ✅ 行动清单
        report_parts.append("## ✅ 行动清单")
        report_parts.append("")
        if important:
            report_parts.append("- [ ] 查看并处理重要邮件")
        report_parts.append("- [ ] 浏览非重要邮件摘要")
        report_parts.append("")

        markdown_content = "\n".join(report_parts)

        return {
            'format': 'markdown',
            'full_content': markdown_content,
            'highlights': [f"共收到 {len(scored_threads)} 个邮件线程"] + (["请优先查看重要邮件"] if important else []),
            'todos': ["查看并处理重要邮件"] if important else ["查看今日邮件"],
            'sections': {}
        }

    @staticmethod
    def _parse_markdown_report(markdown_content: str) -> Dict[str, Any]:
        """
        从 Markdown 报告中提取结构化数据

        提取：
        - highlights（从"今日重点"或"重点"章节）
        - todos（从"待办"或"任务"章节）
        - 完整 markdown（用于显示）

        返回与数据库存储兼容的结构

        Args:
            markdown_content: Markdown 格式的报告内容

        Returns:
            包含结构化数据的字典
        """
        result = {
            'format': 'markdown',
            'full_content': markdown_content,
            'highlights': [],
            'todos': [],
            'sections': {}
        }

        try:
            # 使用正则提取章节：## 章节名\n内容...
            sections = re.split(r'\n##\s+', markdown_content)

            for section in sections:
                if not section.strip():
                    continue

                # 提取章节标题和内容
                lines = section.split('\n', 1)
                if len(lines) < 2:
                    continue

                title = lines[0].strip()
                content = lines[1].strip()

                # 存储章节
                result['sections'][title] = content

                # 识别"重点"、"待办"等关键词
                title_lower = title.lower()

                if any(keyword in title_lower for keyword in ['重点', 'highlight', '发现']):
                    # 提取列表项
                    items = re.findall(r'^[-*]\s+(.+)$', content, re.MULTILINE)
                    result['highlights'].extend(items[:7])

                elif any(keyword in title_lower for keyword in ['待办', 'todo', '任务', 'task']):
                    # 提取列表项
                    items = re.findall(r'^[-*\[\]]\s+(.+)$', content, re.MULTILINE)
                    # 清理复选框标记
                    cleaned_items = [re.sub(r'^\[.\]\s*', '', item) for item in items]
                    result['todos'].extend(cleaned_items)

            # 如果没有提取到 highlights，尝试从第一段提取
            if not result['highlights'] and markdown_content:
                first_lines = markdown_content.split('\n\n')[0]
                if first_lines:
                    result['highlights'].append(first_lines[:200])

        except Exception as e:
            logger.warning(f"解析 Markdown 报告时出错: {e}")
            # 失败时至少保留完整内容
            result['highlights'] = ['报告已生成，请查看完整内容']

        return result

    @staticmethod
    def _fix_report_structure(summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        修复不完整的报告结构

        Args:
            summary: 原始报告

        Returns:
            修复后的报告
        """
        # Markdown 格式
        if summary.get('format') == 'markdown':
            if 'full_content' not in summary:
                summary['full_content'] = '报告生成中出现异常'
            if 'highlights' not in summary:
                summary['highlights'] = ['报告生成中出现异常']
            if 'todos' not in summary:
                summary['todos'] = []
            return summary

        # JSON 格式（兼容旧数据）
        if 'highlights' not in summary:
            summary['highlights'] = ['报告生成中出现异常']

        if 'todos' not in summary:
            summary['todos'] = []

        if 'categories' not in summary:
            summary['categories'] = {
                'action_required': [],
                'important': [],
                'billing': [],
                'social': [],
                'other': []
            }

        return summary
