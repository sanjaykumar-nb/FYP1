from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# SQLite uses NullPool, which rejects pool_size/max_overflow outright. The
# models are deliberately dialect-neutral (see models/base.py) so the same code
# runs on SQLite for tests and local runs without Postgres — the engine config
# has to be dialect-aware too, or startup fails with a TypeError.
_engine_kwargs = {"echo": settings.DEBUG}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# Nullable columns added after their table first shipped. create_all never alters
# an existing table, so a database created before them would fail on every query
# that touches the table; each is added once, if missing. (The MVP has no Alembic
# migrations yet; these belong there once it does.)
_ADDED_COLUMNS = [("milestones", "start_date", "DATE")]


def _add_missing_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    for table, column, ddl_type in _ADDED_COLUMNS:
        if inspector.has_table(table) and column not in {c["name"] for c in inspector.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def close_db() -> None:
    await engine.dispose()