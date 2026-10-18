#!/usr/bin/env python3
"""Render non-secret image tokens into a NEW directory; never deploy anything."""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

TOKEN = re.compile(r"(?<![A-Za-z0-9_])__([A-Z][A-Z0-9_]*)__(?![A-Za-z0-9_])")
KEY = re.compile(r"[A-Z][A-Z0-9_]*_IMAGE")
IMAGE = re.compile(r"[a-z0-9][a-z0-9._:/-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]*|@sha256:[a-f0-9]{64})")


def load_values(path):
    """Read literal KEY=image lines. No shell evaluation or credential support."""
    values = {}
    for number, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not KEY.fullmatch(key):
            raise ValueError(f"Invalid image variable at line {number}; only *_IMAGE keys are accepted")
        if key in values:
            raise ValueError(f"Duplicate image variable: {key}")
        if (
            not IMAGE.fullmatch(value)
            or TOKEN.search(value)
            or value.endswith(":latest")
            or "REPLACE" in value
        ):
            raise ValueError(f"Provide a versioned image reference for {key}; values are never evaluated")
        values[key] = value
    if "AIRFLOW_IMAGE" in values:
        image = values["AIRFLOW_IMAGE"]
        if "@" in image:
            raise ValueError("Airflow image must use an explicit tag for this chart mapping")
        repository, _, tag = image.rpartition(":")
        values["AIRFLOW_REPOSITORY"] = repository
        values["AIRFLOW_TAG"] = tag
    return values


def render(source, values_file, output):
    """Validate the entire source tree before atomically publishing rendered files."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Source and output paths must not overlap")
    if not source.is_dir():
        raise ValueError("Source directory does not exist")
    if output.exists():
        raise ValueError("Output already exists; choose a new directory to preserve existing files")
    values = load_values(values_file)
    rendered, missing = {}, set()
    for path in sorted(source.rglob("*")):
        if path.suffix not in (".yaml", ".yml") or not path.is_file():
            continue
        content = path.read_text()
        if not content.strip():
            continue
        relative = path.relative_to(source)
        for name in TOKEN.findall(content):
            if name not in values:
                missing.add(f"{name} ({relative})")
        rendered[relative] = TOKEN.sub(lambda match: values.get(match[1], match[0]), content)
    if missing:
        raise ValueError("Missing image references: " + ", ".join(sorted(missing)))
    if not rendered:
        raise ValueError("No non-empty YAML files found")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".render-", dir=output.parent))
    try:
        for relative, content in rendered.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return len(rendered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("deploy/k8s"))
    parser.add_argument("--values", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = render(args.source, args.values, args.output)
    except (ValueError, OSError) as exc:
        print(f"Render refused: {exc}", file=sys.stderr)
        return 2
    print(f"Rendered {count} YAML files to {args.output}; nothing was applied or started.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
