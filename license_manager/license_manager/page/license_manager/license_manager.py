from typing import Optional

import frappe
from frappe import _


@frappe.whitelist()
def get_license_status() -> dict:
    """Return a summary of the current license status for the UI.

    Returns:
        A dict with keys: status, license_id, customer, expiry, features,
        node_id (from license file), machine_node_id (computed for this machine).
    """
    from license_manager.utils.crypto import get_active_license
    from license_manager.utils.node_id import get_display_node_id

    machine_node_id = get_display_node_id()

    try:
        license_data = get_active_license()
    except Exception:
        license_data = None

    if license_data is None:
        # Check if there's content stored at all to distinguish "Not Activated" vs "Invalid"
        try:
            doc = frappe.get_single("Site License")
            raw = (doc.get("license_file_content") or "").strip()
            stored_status = "Invalid" if raw else "Not Activated"
        except Exception:
            stored_status = "Not Activated"

        return {
            "status": stored_status,
            "license_id": None,
            "customer": None,
            "expiry": None,
            "features": None,
            "node_id": None,
            "machine_node_id": machine_node_id,
        }

    return {
        "status": "Valid",
        "license_id": license_data.get("license_id"),
        "customer": license_data.get("customer"),
        "expiry": license_data.get("expiry"),
        "features": license_data.get("features") or [],
        "node_id": license_data.get("node_id"),
        "machine_node_id": machine_node_id,
    }


@frappe.whitelist()
def import_license(license_json: str) -> dict:
    """Validate and save a license JSON string to the Site License DocType.

    Args:
        license_json: Raw license file contents as a JSON string.

    Returns:
        ``{"success": True, "message": "..."}`` on success, or
        ``{"success": False, "message": "..."}`` on validation failure.
    """
    from license_manager.utils.crypto import activate_license

    try:
        activate_license(license_json)
    except frappe.ValidationError as exc:
        return {"success": False, "message": str(exc)}
    except Exception as exc:
        return {"success": False, "message": f"Unexpected error: {exc}"}

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
        return {"success": False, "message": f"License validated but could not be saved: {exc}"}

    return {"success": True, "message": _("License activated successfully.")}


@frappe.whitelist()
def deactivate_license() -> dict:
    """Remove the stored license from this site (Administrator only)."""
    if frappe.session.user != "Administrator":
        frappe.throw(_("Only Administrator can deactivate the license."), frappe.PermissionError)

    try:
        frappe.db.sql("DELETE FROM `tabSingles` WHERE doctype='Site License'")
        frappe.db.commit()
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    return {"success": True, "message": _("License deactivated.")}
