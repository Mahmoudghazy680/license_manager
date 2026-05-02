"""
Vendor admin backend for the License Vendor Control page.

All methods are restricted to the Administrator user only.
The private key is never stored — it is passed by the admin per request.
"""

import base64
import json
from datetime import datetime, timezone

import frappe
from frappe import _


def _require_administrator():
    if frappe.session.user != "Administrator":
        frappe.throw(_("Only Administrator can access this page."), frappe.PermissionError)


# ---------------------------------------------------------------------------
# Public whitelisted methods
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_vendor_status() -> dict:
    """Return the current license status and this machine's node ID."""
    _require_administrator()

    from license_manager.utils.node_id import get_display_node_id

    machine_node_id = get_display_node_id()

    try:
        doc = frappe.get_single("Site License")
        status      = doc.get("status") or "Not Activated"
        license_id  = doc.get("license_id") or ""
        customer    = doc.get("customer") or ""
        expiry      = doc.get("expiry") or ""
        node_id     = doc.get("node_id") or ""
        features    = doc.get("features") or ""
    except Exception:
        status = "Not Activated"
        license_id = customer = expiry = node_id = features = ""

    return {
        "machine_node_id": machine_node_id,
        "status": status,
        "license_id": license_id,
        "customer": customer,
        "expiry": expiry,
        "node_id": node_id,
        "features": features,
    }


@frappe.whitelist()
def generate_and_activate(
    customer: str,
    license_id: str,
    node_id: str,
    expiry: str,
    private_key_pem: str,
) -> dict:
    """Sign a new license and immediately activate it on this site.

    Returns:
        {"success": True/False, "message": str, "license_json": str}
    """
    _require_administrator()

    try:
        license_json = _build_and_sign(customer, license_id, node_id, expiry, private_key_pem)
    except Exception as exc:
        return {"success": False, "message": str(exc), "license_json": ""}

    # Validate against this site (runs full crypto + node check)
    from license_manager.utils.crypto import activate_license
    try:
        activate_license(license_json)
    except frappe.ValidationError as exc:
        return {"success": False, "message": str(exc), "license_json": license_json}

    # Persist
    try:
        try:
            doc = frappe.get_single("Site License")
        except frappe.DoesNotExistError:
            doc = frappe.new_doc("Site License")
        doc.license_file_content = license_json
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as exc:
        return {
            "success": False,
            "message": _("Signed but could not save: {0}").format(str(exc)),
            "license_json": license_json,
        }

    return {
        "success": True,
        "message": _("License generated and activated successfully."),
        "license_json": license_json,
    }


@frappe.whitelist()
def generate_license_json(
    customer: str,
    license_id: str,
    node_id: str,
    expiry: str,
    private_key_pem: str,
) -> dict:
    """Sign a license for a *different* machine without activating locally.

    Returns:
        {"success": True/False, "message": str, "license_json": str}
    """
    _require_administrator()

    try:
        license_json = _build_and_sign(customer, license_id, node_id, expiry, private_key_pem)
    except Exception as exc:
        return {"success": False, "message": str(exc), "license_json": ""}

    return {
        "success": True,
        "message": _("License signed. Copy the JSON below and deliver it to the client."),
        "license_json": license_json,
    }


@frappe.whitelist()
def deactivate_license() -> dict:
    """Remove the stored license from this site."""
    _require_administrator()

    try:
        frappe.db.sql("DELETE FROM `tabSingles` WHERE doctype='Site License'")
        frappe.db.commit()
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    return {"success": True, "message": _("License deactivated.")}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_and_sign(
    customer: str,
    license_id: str,
    node_id: str,
    expiry: str,
    private_key_pem: str,
) -> str:
    """Build and sign a license payload. Returns the JSON string."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    # Validate inputs
    for name, val in [("Customer", customer), ("License ID", license_id),
                      ("Node ID", node_id), ("Expiry", expiry), ("Private Key", private_key_pem)]:
        if not (val or "").strip():
            frappe.throw(_("{0} is required.").format(name), frappe.ValidationError)

    # Parse + validate expiry
    try:
        expiry_date = datetime.fromisoformat(expiry.strip()[:10])
    except ValueError:
        frappe.throw(_("Expiry must be a valid date (YYYY-MM-DD)."), frappe.ValidationError)

    if expiry_date.date() < datetime.now(tz=timezone.utc).date():
        frappe.throw(_("Expiry date is in the past."), frappe.ValidationError)

    # Load private key
    try:
        private_key = load_pem_private_key(private_key_pem.strip().encode("utf-8"), password=None)
    except Exception as exc:
        frappe.throw(_("Could not load private key: {0}").format(str(exc)), frappe.ValidationError)

    now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    expiry_iso = f"{expiry.strip()[:10]}T23:59:59Z"

    payload = {
        "license_id": license_id.strip(),
        "customer": customer.strip(),
        "issue_date": now_iso,
        "expiry": expiry_iso,
        "node_id": node_id.strip(),
    }

    serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = base64.b64encode(private_key.sign(serialized)).decode("ascii")
    payload["signature"] = signature

    return json.dumps(payload, indent=2)
