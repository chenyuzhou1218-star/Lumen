"""Content-addressed blob store: bytes are stored under their sha256 and never modified."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BlobStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:4] / digest

    def put(self, data: bytes) -> str:
        digest = sha256(data)
        target = self.path(digest)
        if target.exists():
            return digest
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return digest

    def get(self, digest: str) -> bytes:
        return self.path(digest).read_bytes()

    def remove(self, digest: str) -> None:
        self.path(digest).unlink(missing_ok=True)

    def exists(self, digest: str) -> bool:
        return self.path(digest).exists()

    def intact(self, digest: str) -> bool:
        """Re-hash the stored bytes. False if missing or tampered with."""
        p = self.path(digest)
        return p.exists() and sha256(p.read_bytes()) == digest
