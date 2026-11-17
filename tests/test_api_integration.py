import httpx
import pytest

from app.core.crypto import encrypt_payload
from app.domain.licensing import license_hash


@pytest.mark.asyncio
async def test_activation_http_errors_and_success(
    api_client: httpx.AsyncClient, test_license_key: str,
) -> None:
    payload = encrypt_payload(test_license_key, {
        "license_key": test_license_key,
        "device": {
            "os_name": "WINDOWS",
            "cpu_arch": "AMD64",
            "cpu_cores": 8,
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "motherboard_id": "BOARD-A",
        },
    })
    request = {"license_hash": license_hash(test_license_key), "payload": payload}

    too_large = await api_client.post("/api/v1/licenses/activate", content=b"x" * 8193)
    assert too_large.status_code == 413

    invalid = await api_client.post("/api/v1/licenses/activate", json={"bad": 1})
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "ACTIVATION_FAILED"

    success = await api_client.post("/api/v1/licenses/activate", json=request)
    assert success.status_code == 201

    duplicate = await api_client.post("/api/v1/licenses/activate", json=request)
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] == "ACTIVATION_FAILED"

    documentation = await api_client.get("/openapi.json")
    assert documentation.status_code == 404
