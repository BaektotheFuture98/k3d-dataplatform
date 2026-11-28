#!/usr/bin/env python3
"""Prepare future service Secrets only with explicit --apply; never print values."""
import argparse
import base64
import json
import secrets
import subprocess
import sys
from urllib.parse import quote

KUBECTL = ["kubectl", "--context", "k3d-dev"]
COMPONENTS = {
    "airflow": ("pipelines", "airflow-metadata"),
    "jupyter": ("pipelines", "jupyter-auth"),
    "neo4j": ("finance-platform", "neo4j-auth"),
    "spark": ("pipelines", "garage-credentials"),
}


def airflow_fields(password, host="postgres"):
    if not password:
        raise ValueError("PostgreSQL airflow password must be nonempty")
    return {"connection": f"postgresql://airflow_user:{quote(password, safe='')}@{host}:5432/airflow_meta"}


def neo4j_fields(password):
    if not password:
        raise ValueError("Neo4j password must be nonempty")
    return {"NEO4J_AUTH": "neo4j/" + password, "neo4j-password": password}


def api(namespace, args, payload=None):
    result = subprocess.run(
        KUBECTL + ["-n", namespace] + args, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True,
    )
    if result.returncode:
        # API/admission errors can echo Secret payloads; do not expose stderr.
        raise RuntimeError("Kubernetes request failed; check context/RBAC without dumping Secrets")
    return result.stdout


def prepare(component):
    namespace, name = COMPONENTS[component]
    if api(namespace, ["get", "secret", name, "--ignore-not-found", "-o", "name"]).strip():
        print(f"{name}: existing Secret preserved")
        return
    if component == "airflow":
        source = json.loads(api("lakehouse", ["get", "secret", "postgres-credentials", "-o", "json"]))
        password = base64.b64decode(source["data"]["airflow-password"], validate=True).decode()
        fields = airflow_fields(password, "postgres.lakehouse.svc.cluster.local")
    elif component == "spark":
        source = json.loads(api("lakehouse", ["get", "secret", "garage-credentials", "-o", "json"]))
        fields = {
            key: base64.b64decode(source["data"][key], validate=True).decode()
            for key in ("s3-access-key-id", "s3-secret-access-key")
        }
    elif component == "neo4j":
        pvcs = json.loads(api(namespace, ["get", "pvc", "-o", "json"]))
        if any("neo4j" in item["metadata"]["name"] for item in pvcs["items"]):
            raise RuntimeError("Neo4j PVC exists: restore its original Secret instead of generating credentials")
        fields = neo4j_fields(secrets.token_urlsafe(36))
    else:
        fields = {"token": secrets.token_urlsafe(36)}
    manifest = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {
            "name": name, "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": component,
                "app.kubernetes.io/component": "credentials",
                "app.kubernetes.io/part-of": "finance-platform",
                "app.kubernetes.io/managed-by": "platform-config",
            },
        },
        "stringData": fields,
    }
    api(namespace, ["create", "-f", "-"], manifest)
    print(f"{name}: created (values withheld; no files written)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=["all"] + list(COMPONENTS), default="all")
    parser.add_argument("--apply", action="store_true", help="Explicitly create missing Kubernetes Secrets")
    args = parser.parse_args()
    components = list(COMPONENTS) if args.component == "all" else [args.component]
    if not args.apply:
        print("File preparation only. No API request made, no credentials generated.")
        print("Future Secrets: " + ", ".join("/".join(COMPONENTS[c]) for c in components))
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
