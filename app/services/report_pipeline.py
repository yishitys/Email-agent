"""
报告生成管线

串联所有模块，生成完整的邮件报告
"""
import re
from datetime import date, timedelta
from typing import Optional, Dict, Any, List, Tuple

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
            gmail_max_results = getattr(app_config, "GMAIL_MAX_RESULTS", 100)
            if last_n_hours:
                # 最近 N 小时
                messages = SkillGmailFetch.fetch_messages(
                    credentials=credentials,
                    last_n_hours=last_n_hours,
                    max_results=gmail_max_results
                )
                logger.info(f"✓ 拉取了最近 {last_n_hours} 小时的 {len(messages)} 封邮件")
            else:
                # 指定日期（当天 00:00 到 23:59）
                messages = SkillGmailFetch.fetch_messages(
                    credentials=credentials,
                    date_from=report_date,
                    date_to=report_date,
                    max_results=gmail_max_results
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

            truncated_threads = sum(1 for t in threads if getattr(t, "is_truncated", False))
            if truncated_threads:
                logger.warning(f"有 {truncated_threads}/{len(threads)} 个线程因内容过长被截断（ThreadMerge.MAX_COMBINED_LENGTH 限制）")

            # Step 5: 重要性评分
            logger.info("步骤 5/7: 重要性评分")
            scorer = SkillImportanceHeuristics()
            scored_threads = scorer.prioritize_threads(threads)
            logger.info(f"✓ 完成评分，最高分: {scored_threads[0][1]:.1f}" if scored_threads else "✓ 完成评分")

            # Step 6: 生成 Prompt 并调用 AI
            ai_provider = app_config.AI_PROVIDER
            logger.info(f"步骤 6/7: 调用 {ai_provider.upper()} 生成报告")

            try:
                summary = ReportPipeline._generate_ai_summary(
                    scored_threads=scored_threads,
                    report_date=report_date,
                    ai_provider=ai_provider
                )
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
            max_ref_threads = getattr(app_config, "REPORT_MAX_REF_THREADS", 20)
            ref_threads = scored_threads if (max_ref_threads is None or max_ref_threads <= 0) else scored_threads[:max_ref_threads]
            if max_ref_threads is not None and max_ref_threads > 0 and len(scored_threads) > max_ref_threads:
                logger.warning(f"邮件引用仅保存前 {max_ref_threads} 个线程（共 {len(scored_threads)} 个）。可通过 REPORT_MAX_REF_THREADS 调整。")

            for thread, score in ref_threads:
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
    def _generate_ai_summary(
        scored_threads,
        report_date: date,
        ai_provider: str,
    ) -> Dict[str, Any]:
        """
        生成 AI 报告摘要（支持线程分批总结，避免只总结前 N 个线程）
        """
        max_threads_per_prompt = getattr(app_config, "PROMPT_MAX_THREADS", 50)
        if max_threads_per_prompt is None or max_threads_per_prompt <= 0:
            max_threads_per_prompt = len(scored_threads)

        # 分批
        batches = [
            scored_threads[i:i + max_threads_per_prompt]
            for i in range(0, len(scored_threads), max_threads_per_prompt)
        ]

        def call_ai(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
            if ai_provider == "claude":
                ai_client = SkillClaudeSummarize()
                return ai_client.summarize(system_prompt, user_prompt)
            ai_client = SkillGptSummarize()
            return ai_client.summarize(system_prompt, user_prompt)

        # 先对每个 batch 生成一份报告（我们只取其中“重要/非重要”两节，后续统一汇总重点与待办）
        batch_reports: list[Dict[str, Any]] = []
        for idx, batch in enumerate(batches, 1):
            logger.info(f"分批总结线程：{idx}/{len(batches)}（本批 {len(batch)} 个线程）")
            parsed = ReportPipeline._generate_batch_with_coverage_check(
                batch=batch,
                report_date=report_date,
                call_ai=call_ai,
            )
            batch_reports.append(parsed)

        # 汇总“重要邮件/非重要邮件”两节内容
        def pick_section(sections: Dict[str, str], preferred_titles: list[str]) -> str:
            for t in preferred_titles:
                v = sections.get(t)
                if v and v.strip():
                    return v.strip()
            return ""

        important_chunks = []
        non_important_chunks = []
        for br in batch_reports:
            sections = br.get("sections", {}) or {}
            important = pick_section(sections, ["📧 重要邮件", "重要邮件"])
            non_important = pick_section(sections, ["📋 非重要邮件", "非重要邮件"])
            if important:
                important_chunks.append(important)
            if non_important:
                non_important_chunks.append(non_important)

        important_section = "\n\n".join(important_chunks).strip() or "（无）"
        non_important_section = "\n\n".join(non_important_chunks).strip() or "（无）"

        # 基于汇总后的“重要/非重要”章节，再生成一次“今日重点/行动清单”（内容更短、更不易超限）
        finalize_system = "你是一个专业的邮件助手。请用中文 Markdown 输出指定章节，内容要具体、可执行。"
        finalize_user = "\n".join([
            "请根据以下已整理的邮件摘要，生成**仅包含**这两个章节（顺序不可变）：",
            "",
            "## ⚡ 今日重点",
            "",
            "3-5条最关键的发现或待办事项（尽量从重要邮件中提炼）。",
            "",
            "## ✅ 行动清单",
            "",
            "具体的待办事项列表（用 Markdown 列表，可带复选框）。",
            "",
            "---",
            "",
            "以下是整理好的摘要：",
            "",
            "## 📧 重要邮件",
            important_section,
            "",
            "## 📋 非重要邮件",
            non_important_section,
        ])

        finalize_resp = call_ai(finalize_system, finalize_user)
        if finalize_resp.get("format") == "markdown":
            finalize_parsed = ReportPipeline._parse_markdown_report(finalize_resp["content"])
        else:
            finalize_parsed = ReportPipeline._fix_report_structure(finalize_resp)

        final_sections = finalize_parsed.get("sections", {}) or {}
        highlights_body = pick_section(final_sections, ["⚡ 今日重点", "今日重点", "重点"]) or "（无）"
        todos_body = pick_section(final_sections, ["✅ 行动清单", "行动清单", "待办事项", "待办"]) or "（无）"

        full_markdown = "\n".join([
            "## 📧 重要邮件",
            "",
            important_section,
            "",
            "## 📋 非重要邮件",
            "",
            non_important_section,
            "",
            "## ⚡ 今日重点",
            "",
            highlights_body,
            "",
            "## ✅ 行动清单",
            "",
            todos_body,
        ]).strip()

        return ReportPipeline._parse_markdown_report(full_markdown)

    @staticmethod
    def _extract_thread_tags(text: str) -> set:
        """从章节文本中提取 [Txx] 标签集合，如 {'T01', 'T02'}"""
        if not text:
            return set()
        tags = re.findall(r'\[(T\d+)\]', text, re.IGNORECASE)
        return {t.upper() for t in tags}

    @staticmethod
    def _validate_batch_coverage(parsed: Dict[str, Any], batch_size: int) -> Tuple[bool, set]:
        """
        校验重要+非重要章节中 [Txx] 是否覆盖全部线程。
        Returns: (是否通过, 缺失的标签集合)
        """
        def pick_section(sections: Dict[str, str], preferred_titles: list[str]) -> str:
            for t in preferred_titles:
                v = sections.get(t)
                if v and v.strip():
                    return v.strip()
            return ""

        sections = parsed.get("sections", {}) or {}
        important = pick_section(sections, ["📧 重要邮件", "重要邮件"])
        non_important = pick_section(sections, ["📋 非重要邮件", "非重要邮件"])
        found = ReportPipeline._extract_thread_tags(important) | ReportPipeline._extract_thread_tags(non_important)
        expected = {f"T{i:02d}" for i in range(1, batch_size + 1)}
        missing = expected - found
        return (len(missing) == 0, missing)

    @staticmethod
    def _generate_batch_with_coverage_check(
        batch: list,
        report_date: date,
        call_ai,
    ) -> Dict[str, Any]:
        """
        生成单个 batch 的报告，若覆盖率不足则发起补齐重试。
        """
        system_prompt, user_prompt = SkillPromptCompose.compose(batch, report_date)
        ai_response = call_ai(system_prompt, user_prompt)

        if ai_response.get("format") == "markdown":
            parsed = ReportPipeline._parse_markdown_report(ai_response["content"])
        else:
            parsed = ai_response
            parsed = ReportPipeline._fix_report_structure(parsed)

        ok, missing = ReportPipeline._validate_batch_coverage(parsed, len(batch))
        if ok:
            return parsed

        logger.warning(f"本批 {len(batch)} 个线程，缺失 {len(missing)} 条: {sorted(missing)}，发起补齐重试")
        supplement = ReportPipeline._generate_supplement_for_missing(
            batch=batch,
            report_date=report_date,
            missing_tags=missing,
            call_ai=call_ai,
        )
        if supplement:
            parsed = ReportPipeline._merge_supplement_into_parsed(parsed, supplement)
            ok2, missing2 = ReportPipeline._validate_batch_coverage(parsed, len(batch))
            if not ok2:
                logger.warning(f"补齐后仍缺失 {len(missing2)} 条: {sorted(missing2)}")
        return parsed

    @staticmethod
    def _generate_supplement_for_missing(
        batch: list,
        report_date: date,
        missing_tags: set,
        call_ai,
    ) -> Optional[Dict[str, str]]:
        """
        为缺失的 [Txx] 生成补齐内容。返回 {'important': str, 'non_important': str} 或 None。
        """
        # 建立 tag -> (thread, score) 映射
        tag_to_item = {}
        for i, (thread, score) in enumerate(batch, 1):
            tag = f"T{i:02d}"
            tag_to_item[tag] = (thread, score)

        missing_list = sorted(missing_tags)
        supplement_threads = []
        for tag in missing_list:
            if tag in tag_to_item:
                supplement_threads.append((tag, tag_to_item[tag]))

        if not supplement_threads:
            return None

        # 构建仅包含缺失线程的 prompt
        user_parts = [
            f"以下 {len(supplement_threads)} 个线程在之前的报告中遗漏，请**仅**为它们输出条目，格式与之前相同。",
            "",
            "缺失的线程及其在输出中的标签：",
            ""
        ]
        for tag, (thread, score) in supplement_threads:
            user_parts.append(f"### [{tag}] 线程 (重要性: {score:.1f})")
            user_parts.append(f"主题: {thread.subject}")
            user_parts.append(f"邮件数: {thread.total_messages}")
            if thread.participants:
                user_parts.append(f"参与者: {', '.join(thread.participants[:3])}")
            if thread.has_attachments:
                user_parts.append("📎 包含附件")
            user_parts.append(f"内容:\n{thread.combined_text[:2000]}")  # 限制长度
            user_parts.append("")

        user_parts.append("请按以下格式输出，分数>=20 的放入 ## 📧 重要邮件，<20 的放入 ## 📋 非重要邮件：")
        user_parts.append("- 重要: **[Txx] 主题** + 发件人、时间、内容摘要")
        user_parts.append("- 非重要: **[Txx] 主题** — **发件人**: xxx。一句话摘要。")

        sup_system = "你是一个专业的邮件助手。请严格按照格式输出，每条标题必须以对应的 [Txx] 开头。"
        sup_user = "\n".join(user_parts)

        try:
            resp = call_ai(sup_system, sup_user)
            content = resp.get("content", "").strip() if resp.get("format") == "markdown" else ""
            if not content:
                return None
            sup_parsed = ReportPipeline._parse_markdown_report(content)
            sections = sup_parsed.get("sections", {}) or {}
            important = sections.get("📧 重要邮件", "").strip() or sections.get("重要邮件", "").strip()
            non_important = sections.get("📋 非重要邮件", "").strip() or sections.get("非重要邮件", "").strip()
            return {"important": important, "non_important": non_important}
        except Exception as e:
            logger.warning(f"补齐重试失败: {e}")
            return None

    @staticmethod
    def _merge_supplement_into_parsed(parsed: Dict[str, Any], supplement: Dict[str, str]) -> Dict[str, Any]:
        """将补齐内容追加到 parsed 的对应章节。"""
        sections = parsed.get("sections", {}) or {}
        imp_key = "📧 重要邮件" if "📧 重要邮件" in sections else "重要邮件"
        non_key = "📋 非重要邮件" if "📋 非重要邮件" in sections else "非重要邮件"

        imp_cur = sections.get(imp_key, "").strip()
        non_cur = sections.get(non_key, "").strip()
        imp_add = (supplement.get("important") or "").strip()
        non_add = (supplement.get("non_important") or "").strip()

        if imp_add:
            sections[imp_key] = (imp_cur + "\n\n" + imp_add).strip() if imp_cur else imp_add
        if non_add:
            sections[non_key] = (non_cur + "\n\n" + non_add).strip() if non_cur else non_add

        parsed["sections"] = sections
        return parsed

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
            # 注意：报告内容通常以 "## ..." 开头，原实现使用 "\n##" 会漏掉首个章节。
            content_for_split = markdown_content
            if not content_for_split.startswith("\n"):
                content_for_split = "\n" + content_for_split
            sections = re.split(r'\n##\s+', content_for_split)

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
                    # 支持 "- xxx" / "* xxx" / "1. xxx" 三种常见格式
                    items = []
                    for m in re.finditer(r'^(?:[-*]|\d+\.)\s+(.+)$', content, re.MULTILINE):
                        items.append(m.group(1).strip())
                    result['highlights'].extend(items[:7])

                elif any(keyword in title_lower for keyword in ['待办', 'todo', '任务', 'task']):
                    # 提取列表项
                    # 支持 "- [ ] xxx" / "- [x] xxx" / "- xxx" / "1. xxx"
                    items = []
                    for m in re.finditer(r'^(?:[-*]|\d+\.)\s+(?:\[[ xX]\]\s*)?(.+)$', content, re.MULTILINE):
                        items.append(m.group(1).strip())
                    result['todos'].extend(items)

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
