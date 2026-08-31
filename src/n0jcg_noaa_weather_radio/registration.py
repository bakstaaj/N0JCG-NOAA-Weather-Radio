from __future__ import annotations

import hashlib
import json
import platform
import secrets
from pathlib import Path

from n0jcg_licensing import LicenseClient

from . import LICENSE_PREFIX, PRODUCT_ID, PRODUCT_NAME, VERSION


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


def _client(state_path: Path) -> LicenseClient:
    return LicenseClient(product_slug=PRODUCT_ID, app_version=VERSION, state_root=state_path.parent / "license")


def registration_status(state_path: Path) -> dict[str, object]:
    installation = installation_id(state_path)
    try:
        saved = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    license_status = _client(state_path).status()
    registered = bool(license_status.get("registered") or saved.get("license_token"))
    return {"product_name": PRODUCT_NAME, "product_id": PRODUCT_ID, "license_prefix": LICENSE_PREFIX, "installation_id": installation, "serial_number": license_status.get("serial_number"), "registered": registered, "mode": "registered" if registered else "unregistered", "license_configured": bool(license_status.get("license_configured")), "license_suffix": license_status.get("license_suffix", ""), "validation_error": license_status.get("validation_error")}


def activate(state_path: Path, license_serial: str, email: str) -> dict[str, object]:
    if not str(license_serial or "").strip().upper().startswith(LICENSE_PREFIX):
        raise ValueError(f"license S/N must start with {LICENSE_PREFIX}")
    _client(state_path).activate(license_serial, email)
    return registration_status(state_path)
