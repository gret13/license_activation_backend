import hashlib
import json
import re

from app.api.v1.schemas import Device

MAC_PATTERN = re.compile(r"[0-9A-F]{12}\Z")
INVALID_BOARD_IDS = frozenset(
    {
        "",
        "0",
        "NONE",
        "UNKNOWN",
        "DEFAULT STRING",
        "TO BE FILLED BY O.E.M.",
        "TO BE FILLED BY OEM",
        "NOT SPECIFIED",
        "SYSTEM SERIAL NUMBER",
        "123456789",
    }
)
CONDENSED = {"000000000000", "FFFFFFFFFFFF"}
MOTHERBOARD: str = "MOTHERBOARD"
MAC: str = "MAC"


def normalize_text(value: str) -> str:
    return " ".join(value.split()).upper()


def normalize_mac(value: str) -> str:
    condensed = re.sub(r"[:.\-\s]", "", value).upper()
    if MAC_PATTERN.fullmatch(condensed) is None or condensed in CONDENSED:
        raise ValueError("invalid mac")
    return ":".join(condensed[i : i + 2] for i in range(0, 12, 2))


def normalize_device(device: Device) -> Device:
    board = normalize_text(device.motherboard_id or "")
    if board in INVALID_BOARD_IDS:
        board = ""
    return Device(
        os_name=normalize_text(device.os_name),
        cpu_arch=normalize_text(device.cpu_arch),
        cpu_cores=device.cpu_cores,
        mac_address=normalize_mac(device.mac_address),
        motherboard_id=board or None,
    )


def fingerprint(device: Device) -> str:
    hardware_source = MOTHERBOARD if device.motherboard_id else MAC
    value = device.motherboard_id or device.mac_address
    encoded = json.dumps(
        {
            "source": hardware_source,
            "value": value,
            "cpu_cores": device.cpu_cores,
            "os_name": device.os_name,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
