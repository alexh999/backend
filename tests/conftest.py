from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.modules.activity import models as activity_models  # noqa: F401
from app.modules.admin import models as admin_models  # noqa: F401
from app.modules.forum import models as forum_models  # noqa: F401
from app.modules.monitoring import models as monitoring_models  # noqa: F401
from app.modules.paper_trading import models as paper_trading_models  # noqa: F401
from app.modules.users import models as user_models  # noqa: F401


@pytest.fixture(autouse=True)
def isolated_default_database(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'default_test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
    get_settings.cache_clear()
    get_engine.cache_clear()

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        get_settings.cache_clear()
        get_engine.cache_clear()
