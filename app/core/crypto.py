"""Deterministic encryption protocol, version 1."""

import base64
import binascii
import json

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HKDF_SALT = b"license-activation-mvp"
HKDF_INFO = b"license-activation/aes-siv/v1"


class InvalidCiphertext(ValueError):
    pass


def derive_key(license_key: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=64, salt=HKDF_SALT, info=HKDF_INFO
    ).derive(license_key.encode("utf-8"))


def canonical_json(data: dict[str, object]) -> bytes:
    return json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def encrypt_payload(license_key: str, data: dict[str, object]) -> str:
    ciphertext = AESSIV(derive_key(license_key)).encrypt(canonical_json(data), [])
    return base64.b64encode(ciphertext).decode("ascii")


def decrypt_payload(license_key: str, payload: str) -> object:
    try:
        raw = base64.b64decode(payload, validate=True)
        plaintext = AESSIV(derive_key(license_key)).decrypt(raw, [])
        return json.loads(plaintext)
    except (InvalidTag, ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise InvalidCiphertext("invalid ciphertext") from exc
