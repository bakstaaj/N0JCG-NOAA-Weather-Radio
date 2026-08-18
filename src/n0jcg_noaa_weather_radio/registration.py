from __future__ import annotations

import hashlib
import json
import platform
import secrets
from pathlib import Path

from . import PRODUCT_ID


def installation_id(state_path: Path) -> str:
    if state_path.exists():
        try:
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            if saved.get("installation_id"):
                return str(saved["installation_id"])
        except (OSError, ValueError):
            pass
    seed = f"{PRODUCT_ID}:{platform.node()}:{secrets.token_hex(16)}".encode()
    value = hashlib.sha256(seed).hexdigest()[:24].upper()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"installation_id": value, "product_id": PRODUCT_ID}, indent=2) + "\n", encoding="utf-8")
    return value


def registration_status(state_path: Path) -> dict[str, object]:
    installation = installation_id(state_path)
    try:
        saved = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return {"product_id": PRODUCT_ID, "installation_id": installation, "registered": bool(saved.get("license_token")), "mode": "registered" if saved.get("license_token") else "trial"}
