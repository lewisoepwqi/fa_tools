from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
# SQLite（本地无 Docker 时的开发库）在 uvicorn 多线程下需放开同线程校验，
# 否则连接被线程池复用时会抛 "SQLite objects created in a thread..."。
# 对 PostgreSQL 等其它数据库无影响。
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, connection_record) -> None:
    """SQLite 默认不强制外键约束，显式开启。对 PostgreSQL 无此回调影响。"""
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
