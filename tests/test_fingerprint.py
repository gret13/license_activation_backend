import pytest

from app.api.v1.schemas import Device, EncryptedActivation
from app.domain.fingerprint import fingerprint, normalize_device, normalize_mac


def device(**changes: object) -> Device:
    fields: dict[str, object] = {
        "os_name": "  windows  11 ", "cpu_arch": "amd64", "cpu_cores": 8,
        "mac_address": "aa-bb-cc-dd-ee-ff", "motherboard_id": " board  123 ",
    }
    fields.update(changes)
    return Device.model_validate(fields)


def test_stable_fingerprint_and_normalization() -> None:
    normalized = normalize_device(device())
    assert normalized.os_name == "WINDOWS 11"
    assert normalized.motherboard_id == "BOARD 123"
    assert normalized.mac_address == "AA:BB:CC:DD:EE:FF"
    same = normalize_device(device(cpu_arch="arm64", mac_address="11:22:33:44:55:66"))
    assert fingerprint(normalized) == fingerprint(same)


def test_board_fallback_to_mac() -> None:
    first = normalize_device(device(motherboard_id="To Be Filled By O.E.M."))
    second = normalize_device(device(motherboard_id=None))
    assert first.motherboard_id is None
    assert fingerprint(first) == fingerprint(second)
    changed = normalize_device(device(motherboard_id=None, mac_address="11:22:33:44:55:66"))
    assert fingerprint(first) != fingerprint(changed)


def test_schema_strict_types_and_unknown_fields() -> None:
    with pytest.raises(ValueError):
        device(cpu_cores="8")
    with pytest.raises(ValueError):
        device(cpu_cores=-1)
    with pytest.raises(ValueError):
        EncryptedActivation.model_validate({
            "license_key": "Ds23-Da34-We21-E334", "device": device().model_dump(),
            "unexpected": 1,
        })
    with pytest.raises(ValueError):
        normalize_mac("invalid")
