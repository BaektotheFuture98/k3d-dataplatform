#!/usr/bin/env python3
"""Create credentials once without passwords in files, argv, or stdout."""
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
    if exists("secret", "postgres-credentials"):
        print("Existing postgres-credentials preserved; no rotation performed.")
        return
    if exists("pvc", "data-postgres-0"):
        raise SystemExit("Existing PostgreSQL PVC: restore its original Secret; refusing new credentials.")
    secret = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {
            "name": "postgres-credentials", "namespace": "finance-platform",
            "labels": {
                "app.kubernetes.io/name": "postgres",
                "app.kubernetes.io/component": "database",
                "app.kubernetes.io/part-of": "finance-platform",
                "app.kubernetes.io/managed-by": "kubectl",
            },
        },
        "stringData": {
            key: secrets.token_urlsafe(36)
            for key in ("postgres-password", "airflow-password", "iceberg-password")
        },
    }
    # Never print a failed API response: admission webhooks could echo the object.
    result = subprocess.run(
        KUBECTL + ["create", "-f", "-"], input=json.dumps(secret),
        text=True, capture_output=True,
    )
    if result.returncode:
        raise SystemExit("Secret creation failed; inspect API/RBAC without printing credentials.")
    print("secret/postgres-credentials created (values not displayed or saved).")


if __name__ == "__main__":
    main()
