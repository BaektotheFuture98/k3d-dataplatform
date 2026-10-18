#!/usr/bin/env python3
"""Prepare future service Secrets only with explicit --apply; never print values."""
import argparse
import base64
import json
import secrets
import subprocess
import sys
from urllib.parse import quote

KUBECTL = ["kubectl", "--context", "k3d-dev", "-n", "finance-platform"]
COMPONENTS = {"airflow": "airflow-metadata", "jupyter": "jupyter-auth", "neo4j": "neo4j-auth"}


def airflow_fields(password):
    if not password:
        raise ValueError("PostgreSQL airflow password must be nonempty")
    return {"connection": f"postgresql://airflow_user:{quote(password, safe='')}@postgres:5432/airflow_meta"}


def neo4j_fields(password):
    if not password:
        raise ValueError("Neo4j password must be nonempty")
    return {"NEO4J_AUTH": "neo4j/" + password, "neo4j-password": password}


def api(args, payload=None):
    result = subprocess.run(
        KUBECTL + args, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True,
    )
    if result.returncode:
        # API/admission errors can echo Secret payloads; do not expose stderr.
        raise RuntimeError("Kubernetes request failed; check context/RBAC without dumping Secrets")
    return result.stdout


def prepare(component):
    name = COMPONENTS[component]
    if api(["get", "secret", name, "--ignore-not-found", "-o", "name"]).strip():
        print(f"{name}: existing Secret preserved")
        return
    if component == "airflow":
        source = json.loads(api(["get", "secret", "postgres-credentials", "-o", "json"]))
        fields = airflow_fields(base64.b64decode(source["data"]["airflow-password"], validate=True).decode())
    elif component == "neo4j":
        pvcs = json.loads(api(["get", "pvc", "-o", "json"]))
        if any("neo4j" in item["metadata"]["name"] for item in pvcs["items"]):
            raise RuntimeError("Neo4j PVC exists: restore its original Secret instead of generating credentials")
        fields = neo4j_fields(secrets.token_urlsafe(36))
    else:
        fields = {"token": secrets.token_urlsafe(36)}
    manifest = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {
            "name": name, "namespace": "finance-platform",
            "labels": {
                "app.kubernetes.io/name": component,
                "app.kubernetes.io/component": "credentials",
                "app.kubernetes.io/part-of": "finance-platform",
                "app.kubernetes.io/managed-by": "platform-config",
            },
        },
        "stringData": fields,
    }
    api(["create", "-f", "-"], manifest)
    print(f"{name}: created (values withheld; no files written)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=["all"] + list(COMPONENTS), default="all")
    parser.add_argument("--apply", action="store_true", help="Explicitly create missing Kubernetes Secrets")
    args = parser.parse_args()
    components = list(COMPONENTS) if args.component == "all" else [args.component]
    if not args.apply:
        print("File preparation only. No API request made, no credentials generated.")
        print("Future Secrets: " + ", ".join(COMPONENTS[c] for c in components))
        return 0
    try:
        for component in components:
            prepare(component)
    except (RuntimeError, ValueError, KeyError, OSError):
        print("Secret preparation stopped; check source Secret/context/RBAC and preserve existing credentials.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
