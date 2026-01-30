"""
OAuth 认证路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse

from app.integrations.gmail.auth import SkillGmailAuth, AuthError
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/google")
async def google_auth():
    """
    发起 Google OAuth 认证

    重定向用户到 Google 授权页面
    """
    try:
        auth_url = SkillGmailAuth.get_authorization_url()
        logger.info("重定向到 Google 授权页面")
        return RedirectResponse(url=auth_url)
    except AuthError as e:
        logger.error(f"生成授权 URL 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/google/callback")
async def google_auth_callback(
    code: str = Query(..., description="授权码"),
    error: str = Query(None, description="错误信息")
):
    """
    Google OAuth 回调端点

    接收授权码并换取访问令牌
    """
    # 检查是否有错误
    if error:
        logger.error(f"OAuth 授权失败: {error}")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": error, "message": "授权被拒绝"}
        )

    try:
        # 使用授权码换取令牌
        credentials = SkillGmailAuth.exchange_code_for_token(code)
        logger.info("OAuth 授权成功")

        return JSONResponse(content={
            "ok": True,
            "message": "授权成功！您现在可以使用 Gmail API 了。",
            "redirect": "/"
        })

    except AuthError as e:
        logger.error(f"换取令牌失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def auth_status():
    """
    检查认证状态
    """
    is_authed = SkillGmailAuth.check_credentials()

    return {
        "authenticated": is_authed,
        "message": "已授权" if is_authed else "未授权，请访问 /auth/google 进行授权"
    }


@router.post("/revoke")
async def revoke_auth():
    """
    撤销授权
    """
    try:
        success = SkillGmailAuth.revoke_credentials()
        if success:
            logger.info("授权已撤销")
            return {"ok": True, "message": "授权已撤销"}
        else:
            return {"ok": False, "message": "没有可撤销的授权"}
    except Exception as e:
        logger.error(f"撤销授权失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
