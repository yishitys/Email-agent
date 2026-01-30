"""
数据库会话管理
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import config
from app.core.logging import get_logger
from app.db.models import Base

logger = get_logger(__name__)

# 创建引擎
# SQLite 连接字符串格式：sqlite:///path/to/database.db
# check_same_thread=False 允许多线程使用（SQLite 默认限制）
engine = create_engine(
    f"sqlite:///{config.DATABASE_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,  # 设置为 True 可以看到 SQL 语句日志
)

# 创建 SessionLocal 类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    初始化数据库，创建所有表

    在应用启动时调用
    """
    logger.info(f"初始化数据库: {config.DATABASE_PATH}")

    # 确保 data 目录存在
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 创建所有表
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的上下文管理器

    使用方式：
        with get_db() as db:
            # 使用 db 进行数据库操作
            pass

    Yields:
        数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    获取数据库会话（用于依赖注入）

    用于 FastAPI 的 Depends 依赖注入

    Yields:
        数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
