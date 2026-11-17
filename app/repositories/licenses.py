from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Activation, License


class LicenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def locked_by_hash(self, digest: str) -> License | None:
        query = select(License).where(License.license_hash == digest).with_for_update()
        return await self.session.scalar(query)

    async def has_activation(self, license_id: int, fingerprint: str) -> bool:
        query = select(Activation.id).where(
            Activation.license_id == license_id, Activation.fingerprint == fingerprint
        )
        return (await self.session.scalar(query)) is not None

    async def count_activations(self, license_id: int) -> int:
        query = select(func.count(Activation.id)).where(Activation.license_id == license_id)
        return int((await self.session.scalar(query)) or 0)

    async def add_activation(self, activation: Activation) -> int:
        self.session.add(activation)
        await self.session.flush()
        return activation.id
