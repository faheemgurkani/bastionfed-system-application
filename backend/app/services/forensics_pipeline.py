from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ForensicsScanResult:
    engine: str
    verdict: str
    confidence: int
    summary: str


class ForensicsScanner(Protocol):
    def scan_sample(self, *, sample_id: str, filename: str, sha256: str) -> ForensicsScanResult: ...


class DefaultForensicsScanner:
    def scan_sample(self, *, sample_id: str, filename: str, sha256: str) -> ForensicsScanResult:
        verdict = "SUSPICIOUS" if sha256.endswith(("a", "b", "c", "d")) else "MALICIOUS"
        confidence = 79 if verdict == "SUSPICIOUS" else 92
        return ForensicsScanResult(
            engine="bastionfed-default-scanner",
            verdict=verdict,
            confidence=confidence,
            summary=f"Queued sample {sample_id} analyzed by the default scanner profile for {filename}.",
        )


_scanner: ForensicsScanner = DefaultForensicsScanner()


def set_forensics_scanner(scanner: ForensicsScanner) -> None:
    global _scanner
    _scanner = scanner


def scan_sample(*, sample_id: str, filename: str, sha256: str) -> ForensicsScanResult:
    return _scanner.scan_sample(sample_id=sample_id, filename=filename, sha256=sha256)
