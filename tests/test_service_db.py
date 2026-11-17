import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.schemas import ActivationRequest
from app.core.crypto import encrypt_payload
from app.db.models import Activation
from app.domain.licensing import license_hash
from app.services.activation import ActivationRejected, ActivationService


def request_for(board: str, license_key: str) -> ActivationRequest:
    return ActivationRequest(
        license_hash=license_hash(license_key),
        payload=encrypt_payload(license_key, {
            "license_key": license_key,
            "device": {
                "os_name": "WINDOWS",
                "cpu_arch": "AMD64",
                "cpu_cores": 8,
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "motherboard_id": board,
            },
        }),
    )


@pytest.mark.asyncio
async def test_activation_transaction_and_limit(
    seeded_sessions: async_sessionmaker[AsyncSession], test_license_key: str,
) -> None:
    async with seeded_sessions() as session:
        success = await ActivationService(session).activate(
            request_for("BOARD-A", test_license_key)
        )
    assert success.license_id > 0

    async with seeded_sessions() as session:
        with pytest.raises(ActivationRejected) as duplicate:
            await ActivationService(session).activate(request_for("BOARD-A", test_license_key))
    assert duplicate.value.reason == "DUPLICATE_FINGERPRINT"

    async with seeded_sessions() as session:
        with pytest.raises(ActivationRejected) as excess:
            await ActivationService(session).activate(request_for("BOARD-B", test_license_key))
    assert excess.value.reason == "LIMIT_REACHED"

    async with seeded_sessions() as session:
        assert await session.scalar(select(func.count(Activation.id))) == 1


@pytest.mark.asyncio
async def test_concurrent_limit_lock(
    seeded_sessions: async_sessionmaker[AsyncSession], test_license_key: str,
) -> None:
    async def one_activation(board: str) -> str:
        async with seeded_sessions() as session:
            try:
                await ActivationService(session).activate(request_for(board, test_license_key))
                return "success"
            except ActivationRejected as exc:
                return exc.reason

    results = await asyncio.gather(one_activation("BOARD-A"), one_activation("BOARD-B"))
    assert sorted(results) == ["LIMIT_REACHED", "success"]

    async with seeded_sessions() as session:
        assert await session.scalar(select(func.count(Activation.id))) == 1
