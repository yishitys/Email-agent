"""
SkillGmailAuth - Gmail OAuth 认证

处理 Gmail API 的 OAuth 2.0 认证流程
"""
import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.core.config import config
from app.core.logging import get_logger

logger = get_logger(__name__)

# Gmail API 权限范围
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class AuthError(Exception):
    """
    认证错误

    当 OAuth 认证失败或需要重新授权时抛出
    """

    def __init__(self, message: str, needs_reauth: bool = False):
        """
        初始化认证错误

        Args:
            message: 错误信息
            needs_reauth: 是否需要重新授权
        """
        super().__init__(message)
        self.needs_reauth = needs_reauth


class SkillGmailAuth:
    """
    Gmail OAuth 认证技能

    提供 OAuth 2.0 认证流程的完整功能
    """

    @staticmethod
    def get_authorization_url(redirect_uri: Optional[str] = None) -> str:
        """
        获取 OAuth 授权 URL

        Args:
            redirect_uri: 重定向 URI，默认使用配置中的 APP_BASE_URL

        Returns:
            授权 URL

        Raises:
            AuthError: 如果 credentials.json 不存在或格式错误
        """
        try:
            if not config.GMAIL_CREDENTIALS_PATH.exists():
                raise AuthError(
                    f"credentials.json 文件不存在: {config.GMAIL_CREDENTIALS_PATH}",
                    needs_reauth=True
                )

            # 构建重定向 URI
            if redirect_uri is None:
                redirect_uri = f"{config.APP_BASE_URL}/auth/google/callback"

            # 创建 OAuth 流
            flow = Flow.from_client_secrets_file(
                str(config.GMAIL_CREDENTIALS_PATH),
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )

            # 生成授权 URL
            authorization_url, state = flow.authorization_url(
                access_type='offline',  # 获取 refresh token
                include_granted_scopes='true',
                prompt='consent'  # 强制显示同意屏幕以获取 refresh token
            )

            logger.info(f"生成授权 URL: {authorization_url[:100]}...")
            return authorization_url

        except FileNotFoundError as e:
            raise AuthError(
                f"credentials.json 文件不存在: {config.GMAIL_CREDENTIALS_PATH}",
                needs_reauth=True
            ) from e
        except Exception as e:
            raise AuthError(f"生成授权 URL 失败: {e}", needs_reauth=True) from e

    @staticmethod
    def exchange_code_for_token(
        code: str,
        redirect_uri: Optional[str] = None
    ) -> Credentials:
        """
        使用授权码换取访问令牌

        Args:
            code: 授权码（从重定向 URL 获取）
            redirect_uri: 重定向 URI，必须与授权时使用的相同

        Returns:
            Google Credentials 对象

        Raises:
            AuthError: 如果换取令牌失败
        """
        try:
            if not config.GMAIL_CREDENTIALS_PATH.exists():
                raise AuthError(
                    f"credentials.json 文件不存在: {config.GMAIL_CREDENTIALS_PATH}",
                    needs_reauth=True
                )

            # 构建重定向 URI
            if redirect_uri is None:
                redirect_uri = f"{config.APP_BASE_URL}/auth/google/callback"

            # 创建 OAuth 流
            flow = Flow.from_client_secrets_file(
                str(config.GMAIL_CREDENTIALS_PATH),
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )

            # 使用授权码换取令牌
            flow.fetch_token(code=code)
            credentials = flow.credentials

            # 保存令牌
            SkillGmailAuth._save_token(credentials)

            logger.info("成功换取访问令牌并保存")
            return credentials

        except Exception as e:
            raise AuthError(f"换取访问令牌失败: {e}", needs_reauth=True) from e

    @staticmethod
    def load_credentials() -> Optional[Credentials]:
        """
        加载已保存的凭据

        如果凭据过期，会自动尝试刷新

        Returns:
            有效的 Credentials 对象，如果不存在或刷新失败则返回 None

        Raises:
            AuthError: 如果刷新令牌失败且需要重新授权
        """
        token_path = config.GMAIL_TOKEN_PATH

        # 检查 token 文件是否存在
        if not token_path.exists():
            logger.info(f"Token 文件不存在: {token_path}")
            return None

        try:
            # 加载凭据
            credentials = Credentials.from_authorized_user_file(
                str(token_path),
                SCOPES
            )

            # 检查凭据是否有效
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    # 凭据过期，尝试刷新
                    logger.info("凭据已过期，尝试刷新...")
                    try:
                        credentials.refresh(Request())
                        # 刷新成功，保存新的凭据
                        SkillGmailAuth._save_token(credentials)
                        logger.info("凭据刷新成功")
                        return credentials
                    except Exception as e:
                        logger.error(f"刷新凭据失败: {e}")
                        raise AuthError(
                            "凭据已过期且刷新失败，请重新授权",
                            needs_reauth=True
                        ) from e
                else:
                    logger.warning("凭据无效或缺少 refresh token")
                    return None

            logger.info("成功加载有效凭据")
            return credentials

        except json.JSONDecodeError as e:
            logger.error(f"Token 文件格式错误: {e}")
            return None
        except AuthError:
            # 重新抛出 AuthError
            raise
        except Exception as e:
            logger.error(f"加载凭据失败: {e}")
            return None

    @staticmethod
    def _save_token(credentials: Credentials) -> None:
        """
        保存凭据到文件

        Args:
            credentials: Google Credentials 对象
        """
        token_path = config.GMAIL_TOKEN_PATH

        # 确保目录存在
        token_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存凭据
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
        }

        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)

        logger.info(f"凭据已保存到: {token_path}")

    @staticmethod
    def revoke_credentials() -> bool:
        """
        撤销并删除已保存的凭据

        Returns:
            是否成功删除
        """
        token_path = config.GMAIL_TOKEN_PATH

        if token_path.exists():
            try:
                # 尝试撤销凭据
                credentials = Credentials.from_authorized_user_file(
                    str(token_path),
                    SCOPES
                )
                if credentials and credentials.valid:
                    # 撤销访问权限
                    from google.auth.transport.requests import Request
                    import requests
                    requests.post(
                        'https://oauth2.googleapis.com/revoke',
                        params={'token': credentials.token},
                        headers={'content-type': 'application/x-www-form-urlencoded'}
                    )
                    logger.info("凭据已撤销")
            except Exception as e:
                logger.warning(f"撤销凭据失败（可能已失效）: {e}")

            # 删除 token 文件
            token_path.unlink()
            logger.info(f"Token 文件已删除: {token_path}")
            return True
        else:
            logger.info("Token 文件不存在，无需删除")
            return False

    @staticmethod
    def check_credentials() -> bool:
        """
        检查凭据是否有效

        Returns:
            凭据是否有效且可用
        """
        try:
            credentials = SkillGmailAuth.load_credentials()
            return credentials is not None and credentials.valid
        except AuthError:
            return False
