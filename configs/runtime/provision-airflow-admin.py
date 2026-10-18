#!/usr/bin/env python3
"""Provision FAB Admin using stdin-only credentials; never rotate existing users.

Usage: python3 configs/runtime/provision-airflow-admin.py --pod AIRFLOW_API_SERVER_POD
Requires kubectl access to k3d-dev / finance-platform. Does not display credentials.
"""
import argparse
import base64
import json
import secrets
import re
import subprocess
import sys

BASE = ["kubectl", "--context", "k3d-dev", "-n", "finance-platform"]
STAGE = "startup"
REMOTE = r'''
import contextlib, io, json, sys
payload = json.loads(sys.stdin.read())
stage = "initialize_providers"
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from airflow.providers_manager import ProvidersManager
        ProvidersManager().initialize_providers_configuration()
        from airflow.providers.fab.auth_manager.cli_commands.user_command import get_application_builder
        stage = "builder"
        with get_application_builder() as builder:
            sm = builder.sm
            stage = "find_user"
            user = sm.find_user(username=payload["username"])
            if user:
                if "Admin" not in [role.name for role in user.roles]:
                    raise RuntimeError("Existing user does not have Admin role")
                result = "exists"
            elif payload["action"] == "query":
                result = "absent"
            else:
                stage = "find_role"
                role = sm.find_role("Admin")
                if not role:
                    raise RuntimeError("Admin role missing")
                stage = "add_user"
                user = sm.add_user(payload["username"], "Platform", "Admin",
                                   "admin@localhost", role, payload["password"])
                if not user:
                    raise RuntimeError("Creation failed")
                result = "created"
    print(result)
except BaseException as error:
    print("FAB_FAILURE stage=" + stage + " exception=" + type(error).__name__, file=sys.stderr)
    sys.exit(1)
'''


def run(args, data=None):
    result = subprocess.run(BASE + args, input=data, text=True, capture_output=True)
    if result.returncode:
        diagnostic = re.search(r"FAB_FAILURE stage=[a-z_]+ exception=[A-Za-z_][A-Za-z0-9_]*", result.stderr)
        if diagnostic:
            print(diagnostic.group(0), file=sys.stderr)
        raise RuntimeError("kubectl operation failed; output suppressed to protect credentials")
    return result.stdout


def main():
    global STAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pod", required=True)
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    def fab(action, username, password=None):
        payload = json.dumps(dict(action=action, username=username, password=password))
        return run(["exec", "-i", args.pod, "-c", "api-server", "--", "python", "-c", REMOTE], payload).strip()

    STAGE = "get_secret"
    raw = run(["get", "secret", "airflow-admin", "--ignore-not-found", "-o", "json"])
    if raw.strip():
        STAGE = "decode_secret"
        stored = json.loads(raw)["data"]
        username = base64.b64decode(stored["username"]).decode()
        password = base64.b64decode(stored["password"]).decode()
        if not username or not password:
            raise RuntimeError("Existing Secret has empty credentials")
    else:
        username = args.username
        STAGE = "query_user"
        if fab("query", username) == "exists":
            raise RuntimeError("User exists without airflow-admin Secret; refusing to invent or rotate its password")
        password = secrets.token_urlsafe(32)
        manifest = {"apiVersion": "v1", "kind": "Secret", "metadata": {
            "name": "airflow-admin", "namespace": "finance-platform",
            "labels": {
                "app.kubernetes.io/name": "airflow",
                "app.kubernetes.io/component": "credentials",
                "app.kubernetes.io/part-of": "finance-platform",
                "app.kubernetes.io/managed-by": "platform-config",
            }},
            "type": "Opaque", "stringData": {"username": username, "password": password}}
        STAGE = "create_secret"
        run(["create", "-f", "-"], json.dumps(manifest))
    STAGE = "ensure_user"
    result = fab("create", username, password)
    print("Admin user " + result + "; credentials retained in Secret airflow-admin (not displayed).")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid printing arbitrary exceptions that might contain credential payloads.
        print("Admin provisioning failed: stage=" + STAGE + " exception=" + type(error).__name__ + "; credentials suppressed.", file=sys.stderr)
        sys.exit(1)
