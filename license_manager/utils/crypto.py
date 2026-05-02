"""
Cryptographic core for the license_manager app.

Handles Ed25519 signature verification and all license validation steps.
The vendor holds the private key; only the public key is embedded here.

Flow for license activation:
    raw_json → parse_license → verify_signature → check_expiry → check_node_id
"""

import base64
import json
from datetime import datetime, timezone
from typing import Optional

import frappe
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key


class LicenseExpiredError(frappe.ValidationError):
    """Raised specifically when the license expiry date has passed."""


PUBLIC_KEY_PEM = """\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAgWABDuyS6GgBgSAnnc6K97xYGMBnFozmiZhzpv2SAb4=
-----END PUBLIC KEY-----
"""


def parse_license(raw_json: str) -> dict:
    """Parse a raw JSON string into a license dictionary.

    Args:
        raw_json: The raw license file contents as a JSON string.

    Returns:
        Parsed license data as a Python dictionary.

    Raises:
        frappe.ValidationError: If the JSON is malformed or not an object.
    """
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError) as exc:
        frappe.throw(f"License file contains invalid JSON: {exc}", frappe.ValidationError)

    if not isinstance(data, dict):
        frappe.throw("License file must be a JSON object.", frappe.ValidationError)

    return data


def verify_signature(license_data: dict) -> None:
    """Verify the Ed25519 signature on a license dictionary.

    The signature covers all fields **except** the ``"signature"`` key itself,
    serialized with :func:`json.dumps` using ``sort_keys=True``.

    Args:
        license_data: The full license dict including the ``"signature"`` field.

    Raises:
        frappe.ValidationError: If the signature field is missing, cannot be
            decoded, or does not match the payload.
    """
    if "signature" not in license_data:
        frappe.throw("License file is missing the 'signature' field.", frappe.ValidationError)

    try:
        raw_signature = base64.b64decode(license_data["signature"])
    except Exception:
        frappe.throw("License signature field is not valid base64.", frappe.ValidationError)

    payload_dict = {k: v for k, v in license_data.items() if k != "signature"}
    payload = json.dumps(payload_dict, sort_keys=True).encode("utf-8")

    try:
        public_key: Ed25519PublicKey = load_pem_public_key(PUBLIC_KEY_PEM.encode("utf-8"))
        public_key.verify(raw_signature, payload)
    except InvalidSignature:
        frappe.throw("License signature is invalid.", frappe.ValidationError)
    except Exception as exc:
        frappe.throw(f"Could not load public key or verify signature: {exc}", frappe.ValidationError)


def check_expiry(license_data: dict) -> None:
    """Check that the license has not expired.

    Args:
        license_data: Parsed license dictionary containing an ``"expiry"`` field
            in ISO 8601 UTC format (e.g. ``"2026-12-31T23:59:59Z"``).

    Raises:
        frappe.ValidationError: If the license is expired or the expiry field
            cannot be parsed.
    """
    try:
        expiry_str: str = license_data["expiry"]
        # Handle both "Z" suffix and "+00:00" offset
        expiry_str = expiry_str.replace("Z", "+00:00")
        expiry_dt = datetime.fromisoformat(expiry_str)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError) as exc:
        frappe.throw(f"License expiry field is invalid: {exc}", frappe.ValidationError)

    now = datetime.now(tz=timezone.utc)
    if now > expiry_dt:
        frappe.throw("License has expired.", LicenseExpiredError)


def check_node_id(license_data: dict) -> None:
    """Verify that the license is issued for this machine.

    Args:
        license_data: Parsed license dictionary containing a ``"node_id"`` field.

    Raises:
        frappe.ValidationError: If the license node ID does not match this
            machine's computed node ID.
    """
    from license_manager.utils.node_id import compute as compute_node_id

    machine_node_id = compute_node_id()
    license_node_id = license_data.get("node_id", "")

    if machine_node_id != license_node_id:
        frappe.throw(
            f"License node ID does not match this machine. "
            f"Expected {machine_node_id!r}, got {license_node_id!r}.",
            frappe.ValidationError,
        )


def activate_license(raw_json: str) -> dict:
    """Parse and fully validate a license JSON string.

    Runs the full validation pipeline:
    ``parse_license → verify_signature → check_expiry → check_node_id``

    Args:
        raw_json: Raw license file contents as a JSON string.

    Returns:
        The validated license dictionary on success.

    Raises:
        frappe.ValidationError: Propagated from any sub-function on failure.
    """
    license_data = parse_license(raw_json)
    verify_signature(license_data)
    check_expiry(license_data)
    check_node_id(license_data)
    return license_data


def get_active_license() -> Optional[dict]:
    """Load and validate the currently stored license from the Site License DocType.

    Returns:
        The validated license dictionary, or ``None`` if no license is stored
        or validation fails (callers decide how to react to ``None``).
    """
    try:
        doc = frappe.get_single("Site License")
        raw_json: str = doc.get("license_file_content") or ""
        if not raw_json.strip():
            return None
        return activate_license(raw_json)
    except LicenseExpiredError:
        # Update the stored status to Expired immediately (only write once)
        try:
            stored = frappe.db.get_single_value("Site License", "status")
            if stored != "Expired":
                frappe.db.set_single_value("Site License", "status", "Expired")
                frappe.db.commit()
        except Exception:
            pass
        return None
    except frappe.ValidationError:
        return None
    except Exception:
        return None
