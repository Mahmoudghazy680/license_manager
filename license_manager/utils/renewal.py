"""
Renewal and expiry helper utilities for the license_manager app.
"""

from datetime import datetime, timezone
from typing import Optional


def get_days_until_expiry(license_data: dict) -> int:
    """Compute the number of days remaining until the license expires.

    Args:
        license_data: Validated license dictionary with an ``"expiry"`` field
            in ISO 8601 UTC format.

    Returns:
        Days remaining as a non-negative integer. Returns ``0`` if the license
        is already expired or if the expiry field cannot be parsed.
    """
    try:
        expiry_str: str = license_data["expiry"]
        expiry_str = expiry_str.replace("Z", "+00:00")
        expiry_dt = datetime.fromisoformat(expiry_str)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return 0

    now = datetime.now(tz=timezone.utc)
    delta = expiry_dt - now
    return max(0, delta.days)


def get_warning_message(license_data: dict) -> Optional[str]:
    """Return a human-readable warning if the license is expiring soon or expired.

    Args:
        license_data: Validated license dictionary.

    Returns:
        A warning string if the license is expired or expiring within 30 days,
        otherwise ``None``.
    """
    days = get_days_until_expiry(license_data)

    if days <= 0:
        return "Your license has expired. Please renew immediately."

    if days <= 30:
        return f"Your license expires in {days} day{'s' if days != 1 else ''}. Please contact your vendor."

    return None
