"""
SkillGptSummarize - GPT 总结

调用 OpenAI API 生成邮件报告
"""
import json
import time
from typing import Dict, Any, Optional

from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError

from app.core.config import config
from app.core.logging import get_logger

logger = get_logger(__name__)


class GptError(Exception):
    """GPT 调用错误"""
    pass


class SkillGptSummarize:
    """
    GPT 总结技能

    调用 OpenAI API 生成结构化报告
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        初始化

        Args:
            api_key: OpenAI API key，如果为 None 则从配置读取
            model: 模型名称，如果为 None 则从配置读取
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model = model or config.OPENAI_MODEL

        if not self.api_key:
            raise GptError("OpenAI API key 未配置")

        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"GPT 客户端已初始化，模型: {self.model}")

    def summarize(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        调用 GPT 生成摘要

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_retries: 最大重试次数
            timeout: 超时时间（秒）

        Returns:
            解析后的 JSON 报告

        Raises:
            GptError: 调用失败
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"调用 GPT API（尝试 {attempt + 1}/{max_retries}）...")

                # 调用 API（不强制 JSON 格式，让 AI 自由生成 Markdown）
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,  # 较低的温度以获得更稳定的输出
                    timeout=timeout
                )

                # 提取内容
                content = response.choices[0].message.content

                # 尝试解析为 JSON（兼容旧格式）
                try:
                    if content.strip().startswith('{'):
                        report = json.loads(content)
                        logger.info("GPT 响应解析成功（JSON 格式）")
                        return report
                except json.JSONDecodeError:
                    # JSON 解析失败，假定是 Markdown 格式
                    pass

                # 返回 Markdown 格式
                logger.info("GPT 响应解析成功（Markdown 格式）")
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
                    raise GptError(f"速率限制，已重试 {max_retries} 次") from e

            except APITimeoutError as e:
                # 超时
                if attempt < max_retries - 1:
                    logger.warning(f"请求超时，重试中...")
                    time.sleep(5)
                    continue
                else:
                    raise GptError(f"请求超时，已重试 {max_retries} 次") from e

            except APIError as e:
                # API 错误（5xx 服务器错误）
                if e.status_code and e.status_code >= 500 and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"API 服务器错误 ({e.status_code})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise GptError(f"API 错误: {e}") from e

            except Exception as e:
                logger.error(f"GPT 调用失败: {e}")
                raise GptError(f"GPT 调用失败: {e}") from e

        raise GptError("GPT 调用失败，已达到最大重试次数")

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
