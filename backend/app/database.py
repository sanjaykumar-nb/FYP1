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


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()