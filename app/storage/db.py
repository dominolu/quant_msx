from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_db_and_tables() -> None:
    import app.storage.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    table_columns = {
        "grid_strategies": {
            "current_round": (
                "ALTER TABLE grid_strategies "
                "ADD COLUMN current_round INTEGER NOT NULL DEFAULT 0"
            ),
        },
        "grid_fills": {
            "rpnl_usdt": "ALTER TABLE grid_fills ADD COLUMN rpnl_usdt FLOAT NOT NULL DEFAULT 0",
        },
        "account_balance_snapshots": {},
        "scheduler_locks": {},
    }
    with engine.begin() as conn:
        for table, columns in table_columns.items():
            existing = {
                row[1]
                for row in conn.exec_driver_sql(f"PRAGMA table_info('{table}')").fetchall()
            }
            for column, ddl in columns.items():
                if column not in existing:
                    conn.execute(text(ddl))
