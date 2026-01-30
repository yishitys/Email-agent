"""
SkillClaudeSummarize - Claude 总结

调用 Anthropic Claude API 生成邮件报告
"""
import json
import re
import time
from typing import Dict, Any, Optional

from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError

from app.core.config import config
from app.core.logging import get_logger

logger = get_logger(__name__)


def clean_json_control_chars(json_str: str) -> str:
    """
    清理 JSON 字符串中的控制字符

    替换字符串值中未转义的控制字符为转义形式

    Args:
        json_str: 原始 JSON 字符串

    Returns:
        清理后的 JSON 字符串
    """
    def escape_string_content(match):
        """转义字符串内容中的控制字符"""
        content = match.group(1)
        # 转义控制字符
        content = content.replace('\\', '\\\\')  # 先转义反斜杠
        content = content.replace('\n', '\\n')   # 转义换行
        content = content.replace('\r', '\\r')   # 转义回车
        content = content.replace('\t', '\\t')   # 转义制表符
        content = content.replace('"', '\\"')    # 转义双引号
        return f'"{content}"'

    # 匹配 JSON 字符串值（在引号之间的内容）
    # 这个正则会匹配 "..." 形式的字符串，但不处理已经正确转义的情况
    pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"'
    try:
        # 先试试直接解析
        json.loads(json_str)
        return json_str
    except:
        # 解析失败，进行清理
        return re.sub(pattern, escape_string_content, json_str)


class ClaudeError(Exception):
    """Claude 调用错误"""
    pass


class SkillClaudeSummarize:
    """
    Claude 总结技能

    调用 Anthropic Claude API 生成结构化报告
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        初始化

        Args:
            api_key: Anthropic API key，如果为 None 则从配置读取
            model: 模型名称，如果为 None 则使用默认模型
        """
        # 从配置读取（支持 ANTHROPIC_API_KEY 或 OPENAI_API_KEY）
        self.api_key = api_key or getattr(config, 'ANTHROPIC_API_KEY', None) or config.OPENAI_API_KEY
        self.model = model or getattr(config, 'ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')

        if not self.api_key:
            raise ClaudeError("Anthropic API key 未配置")

        self.client = Anthropic(api_key=self.api_key)
        logger.info(f"Claude 客户端已初始化，模型: {self.model}")

    def summarize(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        调用 Claude 生成摘要

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_retries: 最大重试次数
            timeout: 超时时间（秒）

        Returns:
            解析后的 JSON 报告

        Raises:
            ClaudeError: 调用失败
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"调用 Claude API（尝试 {attempt + 1}/{max_retries}）...")

                # 调用 API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=0.3,  # 较低的温度以获得更稳定的输出
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    timeout=timeout
                )

                # 提取内容
                content = response.content[0].text

                # 尝试解析为 JSON（兼容旧格式）
                try:
                    # 尝试提取 JSON（Claude 可能会在 markdown 代码块中返回或添加解释性文字）
                    if '```json' in content:
                        # 提取 ```json ... ``` 中的内容
                        start = content.find('```json') + 7
                        end = content.find('```', start)
                        json_str = content[start:end].strip()
                        report = json.loads(json_str, strict=False)
                        logger.info("Claude 响应解析成功（JSON 格式）")
                        return report
                    elif '{' in content and content.strip().startswith('{'):
                        # 查找第一个 { 并提取到最后一个 }
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        json_str = content[start:end].strip()
                        report = json.loads(json_str, strict=False)
                        logger.info("Claude 响应解析成功（JSON 格式）")
                        return report
                except json.JSONDecodeError:
                    # JSON 解析失败，假定是 Markdown 格式
                    pass

                # 返回 Markdown 格式
                logger.info("Claude 响应解析成功（Markdown 格式）")
                return {
                    'format': 'markdown',
                    'content': content.strip()
                }

            except RateLimitError as e:
                # 速率限制
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10  # 指数退避
                    logger.warning(f"遇到速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ClaudeError(f"速率限制，已重试 {max_retries} 次") from e

            except APITimeoutError as e:
                # 超时
                if attempt < max_retries - 1:
                    logger.warning(f"请求超时，重试中...")
                    time.sleep(5)
                    continue
                else:
                    raise ClaudeError(f"请求超时，已重试 {max_retries} 次") from e

            except APIError as e:
                # API 错误
                if hasattr(e, 'status_code') and e.status_code and e.status_code >= 500 and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"API 服务器错误 ({e.status_code})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ClaudeError(f"API 错误: {e}") from e

            except Exception as e:
                logger.error(f"Claude 调用失败: {e}")
                raise ClaudeError(f"Claude 调用失败: {e}") from e

        raise ClaudeError("Claude 调用失败，已达到最大重试次数")

    def validate_report(self, report: Dict[str, Any]) -> bool:
        """
        验证报告结构

        Args:
            report: 报告字典

        Returns:
            是否有效
        """
        # Markdown 格式验证
        if report.get('format') == 'markdown':
            return bool(report.get('content'))

        # JSON 格式验证（兼容旧数据）
        required_keys = ['highlights', 'todos', 'categories']

        for key in required_keys:
            if key not in report:
                logger.warning(f"报告缺少必需字段: {key}")
                return False

        return True
