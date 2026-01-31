"""
SkillGmailFetch - Gmail 邮件拉取

按时间范围和过滤条件拉取邮件元数据和摘要
"""
import base64
import time
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.logging import get_logger
from app.integrations.gmail.auth import SkillGmailAuth, AuthError

logger = get_logger(__name__)


class MessageSummary:
    """邮件摘要数据类"""

    def __init__(
        self,
        id: str,
        thread_id: str,
        subject: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        date: Optional[datetime] = None,
        snippet: Optional[str] = None,
        labels: Optional[List[str]] = None,
        body_plain: Optional[str] = None,
        cc_addrs: Optional[List[str]] = None,
        attachment_names: Optional[List[str]] = None
    ):
        self.id = id
        self.thread_id = thread_id
        self.subject = subject
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.date = date
        self.snippet = snippet
        self.labels = labels or []
        self.body_plain = body_plain or snippet or ""
        self.cc_addrs = cc_addrs or []
        self.attachment_names = attachment_names or []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'thread_id': self.thread_id,
            'subject': self.subject,
            'from_addr': self.from_addr,
            'to_addr': self.to_addr,
            'date': self.date.isoformat() if self.date else None,
            'snippet': self.snippet,
            'labels': self.labels,
            'body_plain': self.body_plain,
            'cc_addrs': self.cc_addrs,
            'attachment_names': self.attachment_names
        }


class SkillGmailFetch:
    """
    Gmail 邮件拉取技能

    按时间范围和过滤条件拉取邮件
    """

    @staticmethod
    def fetch_messages(
        credentials: Optional[Credentials] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        last_n_hours: Optional[int] = None,
        unread_only: bool = False,
        starred_only: bool = False,
        sender: Optional[str] = None,
        keyword: Optional[str] = None,
        max_results: Optional[int] = 100
    ) -> List[MessageSummary]:
        """
        拉取邮件列表

        Args:
            credentials: Google 凭据，如果为 None 则自动加载
            date_from: 起始日期
            date_to: 结束日期
            last_n_hours: 最近 N 小时（如果指定，则忽略 date_from/date_to）
            unread_only: 只拉取未读邮件
            starred_only: 只拉取星标邮件
            sender: 发件人过滤
            keyword: 关键词搜索
            max_results: 最大返回数量；0/负数/None 表示不限制（会分页拉取直到没有 nextPageToken）

        Returns:
            邮件摘要列表

        Raises:
            AuthError: 认证失败
            Exception: API 调用失败
        """
        # 加载凭据
        if credentials is None:
            credentials = SkillGmailAuth.load_credentials()
            if credentials is None:
                raise AuthError("未找到有效凭据，请先进行授权", needs_reauth=True)

        try:
            # 构建 Gmail API 服务
            service = build('gmail', 'v1', credentials=credentials)

            # 构建查询字符串
            query = SkillGmailFetch._build_query(
                date_from=date_from,
                date_to=date_to,
                last_n_hours=last_n_hours,
                unread_only=unread_only,
                starred_only=starred_only,
                sender=sender,
                keyword=keyword
            )

            logger.info(f"Gmail 查询: {query}")

            # 调用 Gmail API
            messages = []
            page_token = None
            fetched_count = 0

            unlimited = (max_results is None) or (max_results <= 0)

            while unlimited or fetched_count < max_results:
                try:
                    # 列出消息（带重试）
                    results = SkillGmailFetch._list_messages_with_retry(
                        service,
                        query=query,
                        max_results=100 if unlimited else min(max_results - fetched_count, 100),
                        page_token=page_token
                    )

                    if not results.get('messages'):
                        logger.info("没有更多邮件")
                        break

                    # 获取每封邮件的详细信息
                    for msg in results['messages']:
                        try:
                            message_summary = SkillGmailFetch._get_message_summary(
                                service,
                                msg['id']
                            )
                            if message_summary:
                                messages.append(message_summary)
                                fetched_count += 1

                        except Exception as e:
                            logger.warning(f"获取邮件 {msg['id']} 失败: {e}")
                            continue

                    # 检查是否有下一页
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break

                except HttpError as e:
                    if e.resp.status == 429:
                        # 速率限制，等待后重试
                        logger.warning("遇到速率限制，等待 5 秒...")
                        time.sleep(5)
                        continue
                    else:
                        raise

            # 如果触发了上限且还有下一页，提示可能存在未拉取的邮件
            if (not unlimited) and max_results is not None and fetched_count >= max_results and page_token:
                logger.warning(
                    f"已达到 max_results={max_results} 上限，但仍存在下一页（nextPageToken 不为空）。"
                    f" 这会导致部分邮件未被拉取；请提高 GMAIL_MAX_RESULTS 或设置为 0 以不限制。"
                )

            logger.info(f"成功拉取 {len(messages)} 封邮件")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API 错误: {e}")
            if e.resp.status == 401:
                raise AuthError("认证失败，请重新授权", needs_reauth=True) from e
            raise

    @staticmethod
    def _build_query(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        last_n_hours: Optional[int] = None,
        unread_only: bool = False,
        starred_only: bool = False,
        sender: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> str:
        """
        构建 Gmail 查询字符串

        Returns:
            查询字符串
        """
        query_parts = []

        # 时间范围
        if last_n_hours:
            # 最近 N 小时
            query_parts.append(f"newer_than:{last_n_hours}h")
        else:
            # 日期范围
            if date_from:
                query_parts.append(f"after:{date_from.strftime('%Y/%m/%d')}")
            if date_to:
                # Gmail 的 before 是不包含当天的，所以要加 1 天
                next_day = date_to + timedelta(days=1)
                query_parts.append(f"before:{next_day.strftime('%Y/%m/%d')}")

        # 未读
        if unread_only:
            query_parts.append("is:unread")

        # 星标
        if starred_only:
            query_parts.append("is:starred")

        # 发件人
        if sender:
            query_parts.append(f"from:{sender}")

        # 关键词
        if keyword:
            query_parts.append(keyword)

        # 默认：排除垃圾邮件和已删除
        query_parts.append("-in:spam")
        query_parts.append("-in:trash")

        return " ".join(query_parts)

    @staticmethod
    def _list_messages_with_retry(
        service,
        query: str,
        max_results: int,
        page_token: Optional[str] = None,
        max_retries: int = 3
    ):
        """
        列出消息（带重试）

        Args:
            service: Gmail API 服务
            query: 查询字符串
            max_results: 最大结果数
            page_token: 分页令牌
            max_retries: 最大重试次数

        Returns:
            API 响应
        """
        for attempt in range(max_retries):
            try:
                return service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=max_results,
                    pageToken=page_token
                ).execute()
            except HttpError as e:
                if e.resp.status in [500, 503] and attempt < max_retries - 1:
                    # 服务器错误，重试
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"API 错误 {e.resp.status}，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                raise

    @staticmethod
    def _get_message_summary(service, message_id: str) -> Optional[MessageSummary]:
        """
        获取单封邮件的摘要信息

        Args:
            service: Gmail API 服务
            message_id: 邮件 ID

        Returns:
            MessageSummary 对象
        """
        try:
            # 获取完整邮件（包括正文）
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # 解析 headers
            headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}

            # 解析日期
            date_str = headers.get('Date')
            try:
                msg_date = parsedate_to_datetime(date_str) if date_str else None
            except Exception:
                msg_date = None

            # 获取 snippet（摘要）
            snippet = message.get('snippet', '')

            # 获取标签
            labels = message.get('labelIds', [])

            # 提取完整正文
            body_plain = SkillGmailFetch._extract_full_body(message.get('payload', {}))

            # 提取 CC 列表
            cc_str = headers.get('Cc', '')
            cc_addrs = [addr.strip() for addr in cc_str.split(',') if addr.strip()] if cc_str else []

            # 提取附件信息
            attachment_names = SkillGmailFetch._extract_attachments(message.get('payload', {}))

            return MessageSummary(
                id=message_id,
                thread_id=message.get('threadId', ''),
                subject=headers.get('Subject'),
                from_addr=headers.get('From'),
                to_addr=headers.get('To'),
                date=msg_date,
                snippet=snippet,
                labels=labels,
                body_plain=body_plain,
                cc_addrs=cc_addrs,
                attachment_names=attachment_names
            )

        except Exception as e:
            logger.error(f"解析邮件 {message_id} 失败: {e}")
            return None

    @staticmethod
    def _extract_full_body(payload: Dict[str, Any]) -> str:
        """
        从 payload 中提取完整的纯文本正文

        Args:
            payload: 邮件 payload

        Returns:
            纯文本正文
        """
        def get_body_from_part(part):
            """递归提取正文"""
            if 'parts' in part:
                # 多部分消息，递归处理
                text_parts = []
                for subpart in part['parts']:
                    text_parts.append(get_body_from_part(subpart))
                return '\n'.join(filter(None, text_parts))
            else:
                # 单部分消息
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain':
                    # 纯文本
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        try:
                            return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                        except Exception:
                            return ''
                elif mime_type == 'text/html':
                    # HTML（作为后备）
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        try:
                            import re
                            html = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                            # 简单去除 HTML 标签
                            text = re.sub(r'<[^>]+>', '', html)
                            return text
                        except Exception:
                            return ''
            return ''

        try:
            body = get_body_from_part(payload)
            return body.strip() if body else ''
        except Exception as e:
            logger.warning(f"提取邮件正文失败: {e}")
            return ''

    @staticmethod
    def _extract_attachments(payload: Dict[str, Any]) -> List[str]:
        """
        从 payload 中提取附件文件名列表

        Args:
            payload: 邮件 payload

        Returns:
            附件文件名列表
        """
        def get_attachments_from_part(part):
            """递归提取附件"""
            attachments = []
            if 'parts' in part:
                # 多部分消息，递归处理
                for subpart in part['parts']:
                    attachments.extend(get_attachments_from_part(subpart))
            else:
                # 检查是否是附件
                filename = part.get('filename', '')
                if filename:
                    attachments.append(filename)
            return attachments

        try:
            return get_attachments_from_part(payload)
        except Exception as e:
            logger.warning(f"提取附件信息失败: {e}")
            return []
