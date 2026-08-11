from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base


@lru_cache
def get_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args)


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    settings = settings or get_settings()
    return sessionmaker(
        bind=get_engine(settings.database_url),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def init_db(settings: Settings | None = None) -> None:
    from app.modules.paper_trading.models import (
        PaperAccount,
        PaperExecution,
        PaperOrder,
        PaperPosition,
    )

    settings = settings or get_settings()
    Base.metadata.create_all(
        bind=get_engine(settings.database_url),
        tables=[
            PaperAccount.__table__,
            PaperPosition.__table__,
            PaperOrder.__table__,
            PaperExecution.__table__,
        ],
    )


def get_db() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
