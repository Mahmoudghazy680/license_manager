import frappe


def daily_license_check() -> None:
    """Scheduled daily task: warn administrators when the license is expiring.

    Registered under ``scheduler_events.daily`` in hooks.py.

    Behaviour:
    - If no license is present, logs a System Log warning.
    - If the license is expired or expiring within 30 days, sends a warning
      email to every System Manager and creates a System Log entry.
    """
    from license_manager.utils.crypto import LicenseExpiredError, get_active_license
    from license_manager.utils.renewal import get_warning_message

    # Always re-evaluate expiry and sync the stored status field
    _sync_expiry_status()

    license_data = get_active_license()

    if license_data is None:
        frappe.log_error(
            title="License Manager — No Valid License",
            message=(
                "No valid license is installed on this site. "
                "Please import a license file under Setup > License Manager."
            ),
        )
        _notify_admins(
            subject="[License Manager] No valid license installed",
            message=(
                "No valid license is installed on this ERPNext site. "
                "Please import a license file from Setup > License Manager as soon as possible."
            ),
        )
        return

    warning = get_warning_message(license_data)
    if warning:
        frappe.log_error(title="License Manager — Expiry Warning", message=warning)
        _notify_admins(
            subject=f"[License Manager] {warning[:80]}",
            message=warning,
        )


def _notify_admins(subject: str, message: str) -> None:
    """Send an email notification to all System Manager users.

    Args:
        subject: Email subject line.
        message: Plain-text email body.
    """
    try:
        admin_users = frappe.get_all(
            "User",
            filters={"enabled": 1, "name": ("!=", "Administrator")},
            fields=["email", "name"],
        )
        # Filter to users with System Manager role
        admin_emails = []
        for user in admin_users:
            roles = frappe.get_roles(user["name"])
            if "System Manager" in roles:
                if user.get("email"):
                    admin_emails.append(user["email"])

        if admin_emails:
            frappe.sendmail(
                recipients=admin_emails,
                subject=subject,
                message=f"<p>{frappe.utils.escape_html(message)}</p>",
            )
    except Exception as exc:
        frappe.log_error(
            title="License Manager — Failed to notify admins",
            message=str(exc),
        )


def _sync_expiry_status() -> None:
    """Re-evaluate the stored license and set status = 'Expired' if past expiry.

    Safe to call frequently — only writes to the DB when the stored status
    needs to change (Valid → Expired).
    """
    try:
        stored_status = frappe.db.get_single_value("Site License", "status")
        if stored_status != "Valid":
            return  # already not valid, nothing to do

        raw = frappe.db.get_single_value("Site License", "license_file_content") or ""
        if not raw.strip():
            return

        from license_manager.utils.crypto import LicenseExpiredError, activate_license
        try:
            activate_license(raw)
        except LicenseExpiredError:
            frappe.db.set_single_value("Site License", "status", "Expired")
            frappe.db.commit()
    except Exception:
        pass
