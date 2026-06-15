"""PII / secret masking pre-processor.

Runs immediately after log ingestion and *before* any payload is sent to an
external LLM. NeXtrace is a security product, so shipping raw credentials,
secret keys, card numbers or personal data to a third-party inference provider
would itself be a data-governance incident. This module redacts that material
in place.

Design goals
------------
* **Deterministic tokenization** — the same secret value always maps to the
  same placeholder (e.g. ``<REDACTED_EMAIL_1>``), so downstream agents retain
  *referential integrity*: they can still reason that "the same actor appears
  in event A and event C" without ever seeing the real PII.
* **Attribution-safe** — source IPs and usernames are preserved by default,
  because the attribution / GeoIP stages genuinely need them. Only true secrets
  and personal identifiers are masked.
* **Reversible** — the returned mapping lets the UI optionally restore values
  in the final, locally-rendered report (never sent off-box).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


# Ordered most-specific → least-specific so high-entropy secrets win before the
# broad "generic token" catch-all gets a chance to partially match them.
_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    # Private key PEM blocks.
    ("PRIVATE_KEY", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----",
        re.DOTALL,
    )),
    # JSON Web Tokens.
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    # AWS access key IDs.
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA)[0-9A-Z]{16}\b")),
    # Common provider secret tokens (OpenAI sk-, GitHub ghp_/github_pat_, Slack xox...).
    ("API_KEY", re.compile(
        r"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"
    )),
    # Credit-card-like 13–16 digit sequences (loose; Luhn check applied below).
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    # US Social Security Numbers.
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Email addresses.
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # AWS secret access keys (40-char base64) — only when introduced by a hint
    # word, to avoid masking ordinary hashes/IDs.
    ("AWS_SECRET_KEY", re.compile(
        r"(?i)(?:secret[_-]?access[_-]?key|aws[_-]?secret)\W{0,3}([A-Za-z0-9/+]{40})"
    )),
]


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum to reduce credit-card false positives."""
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 16:
        return False
    checksum = 0
    parity = len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        checksum += n
    return checksum % 10 == 0


@dataclass
class MaskResult:
    """Result of masking a blob of text."""

    text: str
    # placeholder -> original value, for optional local restoration.
    mapping: Dict[str, str] = field(default_factory=dict)

    @property
    def redaction_count(self) -> int:
        return len(self.mapping)


class PIIMasker:
    """Deterministic, referential-integrity-preserving PII/secret masker."""

    def __init__(self, mask_ip: bool = False) -> None:
        # Source IPs are needed by attribution + GeoIP, so off by default.
        self.mask_ip = mask_ip
        # value -> placeholder, shared across an entire masking session so the
        # same secret gets the same token everywhere.
        self._value_to_token: Dict[str, str] = {}
        self._counters: Dict[str, int] = {}

    # -- internal ----------------------------------------------------------
    def _token_for(self, category: str, value: str) -> str:
        if value in self._value_to_token:
            return self._value_to_token[value]
        self._counters[category] = self._counters.get(category, 0) + 1
        token = f"<REDACTED_{category}_{self._counters[category]}>"
        self._value_to_token[value] = token
        return token

    # -- public ------------------------------------------------------------
    def mask_text(self, text: str) -> MaskResult:
        if not text:
            return MaskResult(text=text)

        mapping: Dict[str, str] = {}

        def _replace(category: str, raw: str, group: str) -> str:
            token = self._token_for(category, group)
            mapping[token] = group
            # Preserve any hint-word prefix (e.g. "secret_access_key=") so the
            # surrounding log line stays readable while the value is masked.
            return raw.replace(group, token)

        for category, pattern in _PATTERNS:
            def _sub(m: "re.Match[str]", _cat: str = category) -> str:
                raw = m.group(0)
                group = m.group(1) if m.groups() else raw
                if _cat == "CREDIT_CARD" and not _luhn_ok(group):
                    return raw
                return _replace(_cat, raw, group)

            text = pattern.sub(_sub, text)

        if self.mask_ip:
            ip_pat = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

            def _ip_sub(m: "re.Match[str]") -> str:
                raw = m.group(0)
                token = self._token_for("IP", raw)
                mapping[token] = raw
                return token

            text = ip_pat.sub(_ip_sub, text)

        return MaskResult(text=text, mapping=mapping)

    def mask_log_sources(self, sources: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """Mask the ``content`` field of each serialized LogSource dict.

        Returns the masked sources plus the combined placeholder→value mapping.
        """
        combined: Dict[str, str] = {}
        masked_sources: List[Dict[str, Any]] = []
        for src in sources:
            src_copy = dict(src)
            content = src_copy.get("content", "")
            if isinstance(content, str) and content:
                result = self.mask_text(content)
                src_copy["content"] = result.text
                combined.update(result.mapping)
            masked_sources.append(src_copy)
        return masked_sources, combined


def mask_log_sources(
    sources: List[Dict[str, Any]],
    mask_ip: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Convenience wrapper: mask a list of LogSource dicts in one call."""
    masker = PIIMasker(mask_ip=mask_ip)
    return masker.mask_log_sources(sources)
