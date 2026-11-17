import json
import logging
import os
import stat
from pathlib import Path

from app.core.logging import log_event, pseudonym, setup_logging
from app.db.bootstrap import export_if_missing


def test_jsonl_privacy_and_rotation_files(tmp_path: Path) -> None:
    logger = setup_logging(tmp_path)
    try:
        log_event(logging.ERROR, "DATABASE_UNAVAILABLE", request_id="known-id",
                  status_code=503, license_key="sensitive", mac_address="sensitive")
        app = (tmp_path / "app.log").read_text(encoding="utf-8").strip()
        error = (tmp_path / "error.log").read_text(encoding="utf-8").strip()
        assert app == error
        assert json.loads(app)["request_id"] == "known-id"
        assert "sensitive" not in app
        assert pseudonym("a" * 32, "127.0.0.1") == pseudonym("a" * 32, "127.0.0.1")
        assert pseudonym("a" * 32, "127.0.0.1") != pseudonym("b" * 32, "127.0.0.1")
    finally:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()


def test_seed_file_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "secrets" / "test_licenses.txt"
    export_if_missing(["FIRST"], path)
    export_if_missing(["SECOND"], path)
    assert path.read_text() == "FIRST\n"
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
