"""Verify Apache digest files in bare, GNU, BSD or wrapped-hex format."""
import hashlib
from pathlib import Path
import re
import sys

artifact = Path(sys.argv[1])
digest_text = Path(sys.argv[2]).read_text(encoding="ascii")
# Apache mirrors have used both GNU and BSD digest output. Ignore the filename,
# then join whitespace-separated digest blocks (some BSD output wraps them).
digest_text = digest_text.replace(artifact.name, "")
blocks = re.findall(r"(?<![A-Za-z0-9])[0-9a-fA-F]{16,128}(?![A-Za-z0-9])", digest_text)
expected = "".join(blocks).lower()
if len(expected) != 128:
    raise SystemExit("Expected exactly one SHA-512 digest")
actual = hashlib.sha512()
with artifact.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        actual.update(block)
if actual.hexdigest() != expected:
    raise SystemExit("SHA-512 mismatch")
print(f"SHA-512 verified: {artifact.name}")
