#!/usr/bin/env python3
"""Create Garage/S3 credentials once; never print or persist their values."""
import json
import secrets
import subprocess

KUBECTL = ["kubectl", "--context", "k3d-dev", "-n", "finance-platform"]


def exists(kind, name):
    result = subprocess.run(
        KUBECTL + ["get", kind, name, "--ignore-not-found", "-o", "name"],
        check=True, text=True, capture_output=True,
    )
    return bool(result.stdout.strip())


def main():
    if exists("secret", "garage-credentials"):
        print("Existing garage-credentials preserved; no rotation performed.")
        return
    if exists("pvc", "data-garage-0"):
        raise SystemExit("Existing Garage PVC: restore original credentials; refusing replacement.")
    secret = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {
            "name": "garage-credentials", "namespace": "finance-platform",
            "labels": {
                "app.kubernetes.io/name": "garage",
                "app.kubernetes.io/component": "object-storage",
                "app.kubernetes.io/part-of": "finance-platform",
                "app.kubernetes.io/managed-by": "kubectl",
            },
        },
        "stringData": {
            "rpc-secret": secrets.token_hex(32),
            "admin-token": secrets.token_urlsafe(36),
            "s3-access-key-id": "GK" + secrets.token_hex(16),
            "s3-secret-access-key": secrets.token_hex(32),
        },
    }
    result = subprocess.run(
        KUBECTL + ["create", "-f", "-"], input=json.dumps(secret),
        text=True, capture_output=True,
    )
    if result.returncode:
        raise SystemExit("Garage Secret creation failed; inspect API/RBAC without printing credentials.")
    print("secret/garage-credentials created (values not displayed or saved).")


if __name__ == "__main__":
    main()
