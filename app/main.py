"""
Email Agent - FastAPI application entry point
"""
from fastapi import FastAPI

from app.core.config import config
from app.core.logging import get_logger
from app.db.session import init_db
from app.web.routes import auth
from app.web.routes import reports

# 获取日志记录器
logger = get_logger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Email Agent",
    description="Local email daily report generator using Gmail and GPT",
    version="0.1.0"
)

# 挂载路由
app.include_router(auth.router)
app.include_router(reports.router)


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("Email Agent 启动中...")

    # 初始化数据库
    try:
        init_db()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    # 验证配置
    missing = config.validate()
    if missing:
        logger.warning(f"缺失的配置项: {', '.join(missing)}")
        logger.warning("某些功能可能无法正常工作")
    else:
        logger.info("配置验证通过")

    # 输出安全的配置信息（用于调试）
    logger.debug("当前配置:")
    for key, value in config.get_safe_config().items():
        logger.debug(f"  {key}: {value}")

    logger.info("Email Agent 启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("Email Agent 正在关闭...")


@app.get("/health")
async def health_check():
    """
    健康检查端点

    Returns:
        包含应用状态的字典
    """
    logger.debug("健康检查请求")
    return {
        "ok": True,
        "version": "0.1.0",
        "config_valid": len(config.validate()) == 0
    }
