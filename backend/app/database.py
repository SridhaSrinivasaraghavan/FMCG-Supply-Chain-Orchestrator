from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import settings

# Async Engine and Session for FastAPI runtime
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync Engine and Session for background tasks, pandas, and tools
sync_engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()
