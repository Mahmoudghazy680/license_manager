"""
Vendor-side license signing script.

This script runs on the VENDOR'S machine (not on the customer's server).
It creates a signed .lic file that can be imported by the customer via:
  bench --site <site> license-import <path-to.lic>

Usage example::

    python tools/sign_license.py \\
        --customer "Acme Corp" \\
        --license-id "LIC-2026-00001" \\
        --node-id "SITE-A3F9C2B1D4E78F20A1B3C4" \\
        --features "accounts,inventory" \\
        --expiry "2026-12-31" \\
        --private-key /secure/vault/license_private.pem \\
        --output acme_corp.lic

Generate a keypair once with::

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption
    )
    priv = Ed25519PrivateKey.generate()
    pub_pem  = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    priv_pem = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    # Paste pub_pem into PUBLIC_KEY_PEM in license_manager/utils/crypto.py
    # Store priv_pem in a secure vault — NEVER commit it.
"""

import argparse
import base64
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path


def build_payload(
    license_id: str,
    customer: str,
    node_id: str,
    features: list[str],
    expiry: str,
) -> dict:
    today_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    expiry_iso = f"{expiry}T23:59:59Z"
    return {
        "license_id": license_id,
        "customer": customer,
        "issue_date": today_iso,
        "expiry": expiry_iso,
        "features": features,
        "node_id": node_id,
    }


def sign_payload(payload: dict, private_key_path: str) -> str:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    pem_bytes = Path(private_key_path).read_bytes()
    private_key = load_pem_private_key(pem_bytes, password=None)

    serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature_bytes = private_key.sign(serialized)
    return base64.b64encode(signature_bytes).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and sign a license file for license_manager."
    )
    parser.add_argument("--customer", required=True, help="Customer name")
    parser.add_argument("--license-id", required=True, dest="license_id",
                        help="License ID string, e.g. LIC-2026-00001")
    parser.add_argument("--node-id", required=True, dest="node_id",
                        help="Target machine node ID (from: bench license-node-id)")
    parser.add_argument("--features", required=True,
                        help="Comma-separated list of features, e.g. accounts,inventory")
    parser.add_argument("--expiry", required=True,
                        help="Expiry date in YYYY-MM-DD format")
    parser.add_argument("--private-key", required=True, dest="private_key",
                        help="Path to Ed25519 private key PEM file")
    parser.add_argument("--output", default="license.lic",
                        help="Output .lic file path (default: license.lic)")

    args = parser.parse_args()

    # Validate expiry format
    try:
        date.fromisoformat(args.expiry)
    except ValueError:
        print(f"ERROR: --expiry must be in YYYY-MM-DD format, got: {args.expiry!r}", file=sys.stderr)
        sys.exit(1)

    # Validate private key file
    if not Path(args.private_key).exists():
        print(f"ERROR: private key file not found: {args.private_key!r}", file=sys.stderr)
        sys.exit(1)

    features = [f.strip() for f in args.features.split(",") if f.strip()]

    payload = build_payload(
        license_id=args.license_id,
        customer=args.customer,
        node_id=args.node_id,
        features=features,
        expiry=args.expiry,
    )

    signature = sign_payload(payload, args.private_key)
    payload["signature"] = signature

    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"License file written to: {output_path.resolve()}")
    print(f"  License ID : {payload['license_id']}")
    print(f"  Customer   : {payload['customer']}")
    print(f"  Node ID    : {payload['node_id']}")
    print(f"  Features   : {', '.join(payload['features'])}")
    print(f"  Issue date : {payload['issue_date']}")
    print(f"  Expiry     : {payload['expiry']}")


if __name__ == "__main__":
    main()
