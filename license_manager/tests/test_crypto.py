"""
Unit tests for license_manager.utils.crypto and license_manager.utils.node_id.

A real Ed25519 keypair is generated once at module load and used as test
fixtures. The PUBLIC_KEY_PEM in crypto is patched with the test public key
so tests run fully offline without touching the production key.
"""

import base64
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# ── Generate a real test keypair at module level ───────────────────────────
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

_TEST_PRIVATE_KEY = Ed25519PrivateKey.generate()
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()
_TEST_PUBLIC_KEY_PEM: str = _TEST_PUBLIC_KEY.public_bytes(
    Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
).decode("utf-8")

_MACHINE_NODE_ID = "SITE-TESTNODE000000000001"
_FUTURE_EXPIRY = (datetime.now(tz=timezone.utc) + timedelta(days=365)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)
_PAST_EXPIRY = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)


def _make_license(
    node_id: str = _MACHINE_NODE_ID,
    expiry: str = _FUTURE_EXPIRY,
    include_signature: bool = True,
) -> dict:
    """Build a license dict, optionally signed with the test private key."""
    payload = {
        "license_id": "LIC-TEST-00001",
        "customer": "Test Customer",
        "issue_date": "2026-01-01T00:00:00Z",
        "expiry": expiry,
        "features": ["accounts", "inventory"],
        "node_id": node_id,
    }
    if include_signature:
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        sig_bytes = _TEST_PRIVATE_KEY.sign(serialized)
        payload["signature"] = base64.b64encode(sig_bytes).decode("ascii")
    return payload


class TestCrypto(unittest.TestCase):

    def _patch_crypto(self):
        """Context manager: patch PUBLIC_KEY_PEM and node_id.compute together."""
        import license_manager.utils.crypto as crypto_mod

        p1 = patch.object(crypto_mod, "PUBLIC_KEY_PEM", _TEST_PUBLIC_KEY_PEM)
        p2 = patch(
            "license_manager.utils.node_id.compute",
            return_value=_MACHINE_NODE_ID,
        )
        return p1, p2

    # ── 1. Valid license passes ────────────────────────────────────────────
    def test_valid_license_passes(self):
        from license_manager.utils.crypto import activate_license

        license_dict = _make_license()
        p1, p2 = self._patch_crypto()
        with p1, p2:
            result = activate_license(json.dumps(license_dict))
        self.assertEqual(result["license_id"], "LIC-TEST-00001")

    # ── 2. Tampered data fails ─────────────────────────────────────────────
    def test_tampered_data_fails(self):
        import frappe

        from license_manager.utils.crypto import activate_license

        license_dict = _make_license()
        raw = json.dumps(license_dict)
        # Tamper the expiry after signing
        tampered = raw.replace(license_dict["expiry"], "2020-01-01T00:00:00Z")

        p1, p2 = self._patch_crypto()
        with p1, p2:
            with self.assertRaises(frappe.ValidationError) as ctx:
                activate_license(tampered)
        self.assertIn("signature", str(ctx.exception).lower())

    # ── 3. Expired license fails ───────────────────────────────────────────
    def test_expired_license_fails(self):
        import frappe

        from license_manager.utils.crypto import activate_license

        license_dict = _make_license(expiry=_PAST_EXPIRY)
        p1, p2 = self._patch_crypto()
        with p1, p2:
            with self.assertRaises(frappe.ValidationError) as ctx:
                activate_license(json.dumps(license_dict))
        self.assertIn("expired", str(ctx.exception).lower())

    # ── 4. Wrong node ID fails ─────────────────────────────────────────────
    def test_wrong_node_id_fails(self):
        import frappe

        from license_manager.utils.crypto import activate_license

        license_dict = _make_license(node_id="SITE-WRONGNODE000000000")
        import license_manager.utils.crypto as crypto_mod

        p1 = patch.object(crypto_mod, "PUBLIC_KEY_PEM", _TEST_PUBLIC_KEY_PEM)
        p2 = patch(
            "license_manager.utils.node_id.compute",
            return_value="SITE-RIGHTNODE000000000",
        )
        with p1, p2:
            with self.assertRaises(frappe.ValidationError) as ctx:
                activate_license(json.dumps(license_dict))
        self.assertIn("node", str(ctx.exception).lower())

    # ── 5. Missing signature field fails ──────────────────────────────────
    def test_missing_signature_field_fails(self):
        import frappe

        from license_manager.utils.crypto import activate_license

        license_dict = _make_license(include_signature=False)
        p1, p2 = self._patch_crypto()
        with p1, p2:
            with self.assertRaises(frappe.ValidationError) as ctx:
                activate_license(json.dumps(license_dict))
        self.assertIn("signature", str(ctx.exception).lower())

    # ── 6. Malformed JSON fails ────────────────────────────────────────────
    def test_malformed_json_fails(self):
        import frappe

        from license_manager.utils.crypto import activate_license

        p1, p2 = self._patch_crypto()
        with p1, p2:
            with self.assertRaises(frappe.ValidationError) as ctx:
                activate_license("not json {{{{")
        self.assertIn("invalid json", str(ctx.exception).lower())

    # ── 7. Node ID is deterministic ────────────────────────────────────────
    def test_node_id_is_deterministic(self):
        from license_manager.utils.node_id import compute

        # Mock frappe.conf to avoid needing a real site
        with patch("license_manager.utils.node_id.frappe") as mock_frappe:
            mock_frappe.conf.get.return_value = "test_secret"
            result1 = compute()
            result2 = compute()

        self.assertEqual(result1, result2)
        self.assertTrue(result1.startswith("SITE-"))
        self.assertEqual(len(result1), 5 + 24)  # "SITE-" + 24 hex chars


if __name__ == "__main__":
    unittest.main()
