"""
Node ID generator for the license_manager app.

The node ID is a stable, hardware-bound identifier derived from:
  - The first non-loopback MAC address (or uuid.getnode() as fallback)
  - CPU core count
  - Platform hostname
  - The Frappe site secret key (ties the ID to a specific site installation)

Because these attributes only change on hardware replacement or full site
re-installation, the node ID remains constant across restarts, reboots, and
software upgrades — making it suitable for node-locked license enforcement.
"""

import hashlib
import os
import platform
import uuid
from typing import Optional


def _get_mac_address() -> str:
    """Return the MAC address of the first non-loopback network interface."""
    try:
        import fcntl
        import socket
        import struct

        for iface_bytes in os.listdir("/sys/class/net"):
            iface = iface_bytes
            if iface == "lo":
                continue
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack("256s", iface.encode("utf-8")[:15]))
                mac = ":".join(f"{b:02x}" for b in info[18:24])
                if mac != "00:00:00:00:00:00":
                    return mac
            except OSError:
                continue
    except Exception:
        pass
    # Fallback: uuid.getnode() returns the MAC as an integer
    return str(uuid.getnode())


def compute() -> str:
    """Compute and return a stable node ID for this machine/site combination.

    Returns:
        A string of the form ``SITE-XXXXXXXXXXXXXXXXXXXXXXXX`` (24 uppercase
        hex characters after the prefix).

    Example::

        >>> compute()
        'SITE-A3F9C2B1D4E78F20A1B3C4D5'
    """
    try:
        import frappe

        site_secret: str = frappe.conf.get("secret_key", "") or ""
    except Exception:
        site_secret = ""

    mac = _get_mac_address()
    cpu_count = str(os.cpu_count() or 0)
    node_name = platform.node()

    raw = "|".join([mac, cpu_count, node_name, site_secret])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "SITE-" + digest[:24].upper()


def get_display_node_id() -> str:
    """Return the node ID for display, or 'UNAVAILABLE' on any error.

    This is a safe wrapper around :func:`compute` intended for use in UI
    contexts where exceptions must not propagate to the browser.

    Returns:
        The node ID string, or ``"UNAVAILABLE"`` if computation fails.
    """
    try:
        return compute()
    except Exception:
        return "UNAVAILABLE"
