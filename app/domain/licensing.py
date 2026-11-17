import hashlib
import re
import secrets
import string

ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase
BASE = len(ALPHABET)
CHAR_TO_VALUE = {character: value for value, character in enumerate(ALPHABET)}
LICENSE_PATTERN = re.compile(r"[A-Za-z0-9]{4}(?:-[A-Za-z0-9]{4}){3}\Z", re.ASCII)


def checksum_value(text: str) -> int:
    total = 0
    factor = 1
    for character in reversed(text):
        value = CHAR_TO_VALUE[character]
        addend = factor * value
        total += addend // BASE + addend % BASE
        factor = 3 - factor
    return total % BASE


def check_character(first_15: str) -> str:
    if len(first_15) != 15 or any(char not in CHAR_TO_VALUE for char in first_15):
        raise ValueError("Expected 15 case-sensitive Base62 symbols")
    total = 0
    factor = 2
    for character in reversed(first_15):
        addend = factor * CHAR_TO_VALUE[character]
        total += addend // BASE + addend % BASE
        factor = 3 - factor
    return ALPHABET[-total % BASE]


def valid_license(key: str) -> bool:
    return LICENSE_PATTERN.fullmatch(key) is not None and checksum_value(key.replace("-", "")) == 0


def make_license() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(15))
    complete = raw + check_character(raw)
    return "-".join(complete[index : index + 4] for index in range(0, 16, 4))


def license_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
