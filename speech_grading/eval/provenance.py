"""Fingerprint of the scoring code, so a cached grade from older analysis or scoring code is never reused."""
from __future__ import annotations

import hashlib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def scoring_sha256() -> str:
    """sha256 over every speech_grading .py file except ASR backends (ASR has its own provenance) and eval tooling."""
    digest = hashlib.sha256()
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE).as_posix()
        if rel.startswith(("asr/", "eval/")):
            continue
        digest.update(rel.encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))  # CRLF checkouts hash the same as LF
    return digest.hexdigest()
