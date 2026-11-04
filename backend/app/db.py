from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def session_dependency():
    with Session() as session:
        yield session


def owner_dependency():
    # This is deliberately a local installation principal, not account authentication.
    return settings.local_owner
