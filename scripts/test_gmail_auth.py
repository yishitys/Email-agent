"""
测试 Gmail OAuth 认证功能
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.integrations.gmail.auth import SkillGmailAuth, AuthError
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_no_token():
    """测试 1: 无 token 文件时，需要授权"""
    print("=" * 60)
    print("测试 1: 无 token 文件 → 需要授权")
    print("=" * 60)

    # 确保 token 文件不存在
    from app.core.config import config
    if config.GMAIL_TOKEN_PATH.exists():
        config.GMAIL_TOKEN_PATH.unlink()

    credentials = SkillGmailAuth.load_credentials()

    if credentials is None:
        print("✓ 正确返回 None（需要重新授权）")
    else:
        print("✗ 应该返回 None")

    print()


def test_valid_token():
    """测试 2: 有效的 token"""
    print("=" * 60)
    print("测试 2: 有效的 token → 返回 Credentials")
    print("=" * 60)

    from app.core.config import config

    # 创建模拟的有效 token
    mock_token = {
        'token': 'mock_access_token',
        'refresh_token': 'mock_refresh_token',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'client_id': 'mock_client_id',
        'client_secret': 'mock_client_secret',
        'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
    }

    # 保存模拟 token
    config.GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.GMAIL_TOKEN_PATH, 'w') as f:
        json.dump(mock_token, f)

    # Mock Credentials 类
    with patch('app.integrations.gmail.auth.Credentials') as MockCredentials:
        mock_creds = Mock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.token = 'mock_access_token'
        MockCredentials.from_authorized_user_file.return_value = mock_creds

        credentials = SkillGmailAuth.load_credentials()

        if credentials and credentials.valid:
            print("✓ 成功加载有效凭据")
            print(f"  Token: {credentials.token[:20]}...")
        else:
            print("✗ 加载凭据失败")

    print()


def test_expired_token_refresh():
    """测试 3: 过期的 token，自动刷新"""
    print("=" * 60)
    print("测试 3: 过期 token → 自动刷新")
    print("=" * 60)

    from app.core.config import config

    # 创建模拟的过期 token
    mock_token = {
        'token': 'expired_access_token',
        'refresh_token': 'mock_refresh_token',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'client_id': 'mock_client_id',
        'client_secret': 'mock_client_secret',
        'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
    }

    config.GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.GMAIL_TOKEN_PATH, 'w') as f:
        json.dump(mock_token, f)

    # Mock Credentials 和 Request
    with patch('app.integrations.gmail.auth.Credentials') as MockCredentials, \
         patch('app.integrations.gmail.auth.Request') as MockRequest:

        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = 'mock_refresh_token'
        mock_creds.token = 'new_access_token'
        mock_creds.client_id = 'mock_client_id'
        mock_creds.client_secret = 'mock_client_secret'
        mock_creds.token_uri = 'https://oauth2.googleapis.com/token'
        mock_creds.scopes = ['https://www.googleapis.com/auth/gmail.readonly']

        # 刷新后变为有效
        def refresh_side_effect(request):
            mock_creds.valid = True
            mock_creds.expired = False

        mock_creds.refresh = Mock(side_effect=refresh_side_effect)

        MockCredentials.from_authorized_user_file.return_value = mock_creds

        try:
            credentials = SkillGmailAuth.load_credentials()
            if credentials and credentials.valid:
                print("✓ 凭据已过期，成功刷新")
                print(f"  新 Token: {credentials.token[:20]}...")
            else:
                print("✗ 刷新失败")
        except AuthError as e:
            print(f"✗ 抛出 AuthError: {e}")

    print()


def test_expired_token_refresh_fail():
    """测试 4: 过期的 token，刷新失败"""
    print("=" * 60)
    print("测试 4: 过期 token → 刷新失败 → 需要重新授权")
    print("=" * 60)

    from app.core.config import config

    # 创建模拟的过期 token
    mock_token = {
        'token': 'expired_access_token',
        'refresh_token': 'invalid_refresh_token',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'client_id': 'mock_client_id',
        'client_secret': 'mock_client_secret',
        'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
    }

    config.GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.GMAIL_TOKEN_PATH, 'w') as f:
        json.dump(mock_token, f)

    # Mock Credentials 和 Request
    with patch('app.integrations.gmail.auth.Credentials') as MockCredentials, \
         patch('app.integrations.gmail.auth.Request') as MockRequest:

        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = 'invalid_refresh_token'

        # 刷新失败
        mock_creds.refresh = Mock(side_effect=Exception("Invalid refresh token"))

        MockCredentials.from_authorized_user_file.return_value = mock_creds

        try:
            credentials = SkillGmailAuth.load_credentials()
            print("✗ 应该抛出 AuthError")
        except AuthError as e:
            if e.needs_reauth:
                print("✓ 正确抛出 AuthError，需要重新授权")
                print(f"  错误信息: {str(e)}")
            else:
                print("✗ AuthError 缺少 needs_reauth 标志")

    print()


def test_get_authorization_url():
    """测试 5: 生成授权 URL"""
    print("=" * 60)
    print("测试 5: 生成授权 URL")
    print("=" * 60)

    from app.core.config import config

    # 检查 credentials.json 是否存在
    if not config.GMAIL_CREDENTIALS_PATH.exists():
        print(f"⚠ credentials.json 不存在: {config.GMAIL_CREDENTIALS_PATH}")
        print("  跳过此测试（需要真实的 credentials.json 文件）")
        print()
        return

    try:
        # 生成授权 URL
        auth_url = SkillGmailAuth.get_authorization_url()
        print("✓ 成功生成授权 URL")
        print(f"  URL: {auth_url[:80]}...")

        # 验证 URL 包含必要的参数
        if 'https://accounts.google.com/o/oauth2/auth' in auth_url:
            print("✓ URL 格式正确")
        else:
            print("✗ URL 格式可能不正确")

    except AuthError as e:
        print(f"✗ 生成授权 URL 失败: {e}")

    print()


def test_check_credentials():
    """测试 6: 检查凭据状态"""
    print("=" * 60)
    print("测试 6: 检查凭据状态")
    print("=" * 60)

    is_valid = SkillGmailAuth.check_credentials()

    if is_valid:
        print("✓ 凭据有效")
    else:
        print("✓ 凭据无效或不存在（符合预期）")

    print()


def test_revoke_credentials():
    """测试 7: 撤销凭据"""
    print("=" * 60)
    print("测试 7: 撤销凭据")
    print("=" * 60)

    from app.core.config import config

    # 创建一个测试 token
    mock_token = {
        'token': 'test_token',
        'refresh_token': 'test_refresh_token',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'client_id': 'test_client_id',
        'client_secret': 'test_client_secret',
        'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
    }

    config.GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.GMAIL_TOKEN_PATH, 'w') as f:
        json.dump(mock_token, f)

    # Mock requests 模块（因为在函数内部导入）
    with patch('google.auth.transport.requests.Request'), \
         patch('requests.post') as mock_post:
        mock_post.return_value = Mock(status_code=200)

        success = SkillGmailAuth.revoke_credentials()

        if success and not config.GMAIL_TOKEN_PATH.exists():
            print("✓ 凭据已撤销并删除")
        else:
            print("✗ 撤销失败")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Gmail OAuth 认证测试")
    print("=" * 60)
    print()

    test_no_token()
    test_valid_token()
    test_expired_token_refresh()
    test_expired_token_refresh_fail()
    test_get_authorization_url()
    test_check_credentials()
    test_revoke_credentials()

    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)
