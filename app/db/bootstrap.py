"""Idempotent initial schema and one-time test-license seeding."""

import os
import secrets
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base, License
from app.domain.licensing import license_hash, make_license

SECRETS_FILE = Path("secrets/test_licenses.txt")


def export_if_missing(licenses: list[str], path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / (".licenses-" + secrets.token_hex(10))
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(licenses) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            temporary.unlink()
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def bootstrap() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            async with session.begin():
                count = await session.scalar(select(func.count(License.id)))
                if count == 0:
                    generated: set[str] = set()
                    while len(generated) < 10:
                        generated.add(make_license())
                    for key in sorted(generated):
                        session.add(License(license_key=key, license_hash=license_hash(key)))
            query = select(License.license_key).order_by(License.id).limit(10)
            existing = await session.scalars(query)
            export_if_missing(list(existing), SECRETS_FILE)
    finally:
        await engine.dispose()
