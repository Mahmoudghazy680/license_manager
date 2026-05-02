import frappe


def check_license() -> None:
    """Validate the site license on every authenticated request.

    Called via the ``auth_hooks`` entry in hooks.py. The result is cached in
    ``frappe.local`` for the lifetime of the current request to avoid
    repeated disk reads.

    Behaviour:
    - Guest users are always allowed through (no license check).
    - Administrator is always allowed through (to enable license recovery).
    - For all other users, a valid license must be present; otherwise the
      request is blocked with a ``frappe.PermissionError``.
    """
    # Skip for system-level users that must always have access
    user = getattr(frappe.session, "user", None) or "Guest"
    if user in ("Guest", "Administrator"):
        return

    # Use per-request cache to avoid re-reading the DB on every hook call
    if getattr(frappe.local, "_license_checked", False):
        return

    frappe.local._license_checked = True

    from license_manager.utils.crypto import get_active_license

    try:
        license_data = get_active_license()
    except frappe.ValidationError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
        return

    if license_data is None:
        frappe.throw(
            "No valid license found. Please import a license file under "
            "Setup > License Manager.",
            frappe.PermissionError,
        )
