"""Base62 case-sensitivity and deterministic encryption protocol test vectors."""

import base64

import pytest

from app.core.crypto import InvalidCiphertext, decrypt_payload, derive_key, encrypt_payload
from app.domain.licensing import (
    check_character,
    checksum_value,
    license_hash,
    make_license,
    valid_license,
)

KEY = "Ds23-Da34-We21-E334"
DEVICE = {
    "os_name": "WINDOWS", "cpu_arch": "AMD64", "cpu_cores": 8,
    "mac_address": "AA:BB:CC:DD:EE:FF", "motherboard_id": "BOARD-123",
}
EXPECTED_KEY_HEX = (
    "c585cbac48e6c830910cc37d64f6809757fd2accbf6d2bda12ba45766a4d917e"
    "d55f9be3f236e76729e4d10618ceda9efd9a0c4db0c2e5bb51ff2f4e66b77470"
)
EXPECTED_PAYLOAD = (
    "Y6jsK0b1XQ4YgKFMR3y+jKzvD4dMROD/HhsqG5mLY++Z15mwxP4+hvxq/E/rJ9Ng89xFpG2Pbq3oH/"
    "PYY9k3zB5dnNN8YfuC/T9KH6Kd2AFUqyV5ZyqPlcO4FJwYuPumVvgSC7s+f3fJ3vGqRfzsWCHSmhO3"
    "rI91tFyscAcGy4OomwAP7uRmMTdr5bBAMpWrQd5SU7LhPnU3STfyuHSaGtSo6b9xVGgwEhjtNOAOwFrSpouA"
)


def test_luhn_mod62_reference_and_license_creation() -> None:
    assert checksum_value(KEY.replace("-", "")) == 0
    assert check_character("Ds23Da34We21E33") == "4"
    assert valid_license(KEY)
    assert not valid_license("Ds23-Da34-We21-E335")
    assert not valid_license(KEY.lower())
    # The last check character changes when case changes in the first 15 characters.
    distinct_licenses = (
        "ds23-da34-we21-e33f",
        "Ds23-Da34-We21-E334",
        "DS23-DA34-WE21-E33K",
    )
    assert all(valid_license(key) for key in distinct_licenses)
    assert len({license_hash(key) for key in distinct_licenses}) == 3
    assert not valid_license("ds23-da34-we21-e334")
    assert all(valid_license(make_license()) for _ in range(100))


def test_hkdf_and_ciphertext_test_vector() -> None:
    assert derive_key(KEY).hex() == EXPECTED_KEY_HEX
    raw = {"license_key": KEY, "device": DEVICE}
    assert encrypt_payload(KEY, raw) == EXPECTED_PAYLOAD
    assert decrypt_payload(KEY, EXPECTED_PAYLOAD) == raw
    assert encrypt_payload(KEY, raw) == encrypt_payload(KEY, raw)
    assert len(license_hash(KEY)) == 64


def test_tampering_rejected() -> None:
    raw = bytearray(base64.b64decode(EXPECTED_PAYLOAD))
    raw[-1] ^= 1
    with pytest.raises(InvalidCiphertext):
        decrypt_payload(KEY, base64.b64encode(raw).decode("ascii"))
    with pytest.raises(InvalidCiphertext):
        decrypt_payload(KEY, "not @ base64")
