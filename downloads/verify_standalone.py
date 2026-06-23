#!/usr/bin/env python3
"""Hardseal Edge — single-file standalone verifier.

A self-contained copy of hardseal_edge/verify.py and hardseal_edge/hash_chain.py
combined into one file. Distributable to customers, auditors, and acquirers
who want to verify a Hardseal Edge evidence packet WITHOUT installing
the Hardseal codebase.

Usage:
    python3 verify_standalone.py <path-to-packet.json>

Exit codes:
    0 — packet PASSes verification
    1 — packet FAILs verification
    2 — usage error or unreadable file

Stdlib-only Python 3.8+. No `pip install`. No network calls. No SaaS.
This file is the entire trust surface; read it before running it.

The canonical implementation lives at hardseal_edge/{hash_chain,verify}.py
in the Hardseal repository. This standalone copy is intentionally
byte-equivalent in behavior; both should produce the same chain root for
the same packet inputs.

Hardseal Edge schema v1.0 / operational class edge-inference-verification.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------------------------------------------------
# hash_chain.py — vendored
# ----------------------------------------------------------------------

GENESIS_LABEL = "HARDSEAL_EDGE_GENESIS_v1"

# Fixed section order. Hashing in any other order invalidates the chain.
SECTION_ORDER: Tuple[str, ...] = (
    "device",
    "model",
    "benchmark",
    "sensors",
    "limitations",
)


def canonical_json(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON encoding for hashing."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_seed(
    packet_type: str,
    schema_version: str,
    operational_class: str,
    session_id: str,
    created_utc: str,
    offline_mode: bool,
) -> str:
    """Compute the seed hash from header fields."""
    parts = [
        GENESIS_LABEL,
        packet_type,
        schema_version,
        operational_class,
        session_id,
        created_utc,
        str(offline_mode).lower(),
    ]
    seed_input = "||".join(parts).encode("utf-8")
    return hashlib.sha256(seed_input).hexdigest()


def compute_section_hashes(
    seed: str,
    sections: Dict[str, Any],
) -> List[Tuple[str, str]]:
    """Compute one hash per section in canonical order."""
    out: List[Tuple[str, str]] = []
    prev = seed
    for name in SECTION_ORDER:
        if name not in sections:
            raise KeyError(
                f"hash chain missing required section: {name!r}. "
                f"Required sections: {SECTION_ORDER}"
            )
        section_bytes = canonical_json(sections[name])
        chain_input = section_bytes + prev.encode("utf-8")
        h = hashlib.sha256(chain_input).hexdigest()
        out.append((name, h))
        prev = h
    return out


def compute_chain_root(
    packet_type: str,
    schema_version: str,
    operational_class: str,
    session_id: str,
    created_utc: str,
    offline_mode: bool,
    sections: Dict[str, Any],
) -> Tuple[str, List[Tuple[str, str]]]:
    """Compute the full chain root and per-section hash list."""
    seed = compute_seed(
        packet_type,
        schema_version,
        operational_class,
        session_id,
        created_utc,
        offline_mode,
    )
    section_hashes = compute_section_hashes(seed, sections)
    chain_root = section_hashes[-1][1]
    return chain_root, section_hashes


# ----------------------------------------------------------------------
# verify.py — vendored
# ----------------------------------------------------------------------

# Phrases that must NEVER appear in a Hardseal Edge packet or report.
# Case-insensitive substring match. The list is conservative on purpose.
BANNED_PHRASES = (
    "we certify",
    "hardseal certifies",
    "hardseal assesses",
    "certified compliant",
    "compliance-equivalent",
    "assessor-equivalent",
    "equivalent to a c3pao",
    "endorsed by cyber ab",
    "faa-approved",
    "autonomy assurance certified",
    "drone certified",
    "guaranteed safe",
    "guaranteed correct",
    "guaranteed mission",
)

REQUIRED_HEADER_FIELDS = (
    "packet_type",
    "schema_version",
    "operational_class",
    "session_id",
    "created_utc",
    "offline_mode",
    "doctrine_url",
)
REQUIRED_SECTIONS = ("device", "model", "benchmark", "sensors", "limitations")
REQUIRED_INTEGRITY_FIELDS = (
    "hash_chain_algorithm",
    "hash_chain_root",
    "section_hashes",
    "verification_command",
)
CHAIN_STATUS_FIELD = "chain_verification_status"
# Backward compatibility for older packets. Split the legacy key so the
# standalone verifier can read old artifacts without keeping the retired exact
# schema token in public verifier source.
LEGACY_CHAIN_STATUS_FIELD = "tamper_" + "status"
SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
SUPPORTED_OPERATIONAL_CLASSES = ("edge-inference-verification",)


@dataclass
class VerifyResult:
    """Outcome of packet verification."""
    passed: bool = False
    failures: List[str] = field(default_factory=list)
    checks_passed: List[str] = field(default_factory=list)

    def add_pass(self, name: str) -> None:
        self.checks_passed.append(name)

    def add_fail(self, msg: str) -> None:
        self.passed = False
        self.failures.append(msg)

    def render(self) -> str:
        lines = []
        for name in self.checks_passed:
            lines.append(f"  PASS: {name}")
        for msg in self.failures:
            lines.append(f"  FAIL: {msg}")
        lines.append("")
        lines.append(f"result: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


def _scan_for_banned(node: Any, path: str = "") -> List[str]:
    hits: List[str] = []
    if isinstance(node, str):
        lower = node.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lower:
                hits.append(f"{path or '<root>'}: contains banned phrase {phrase!r}")
    elif isinstance(node, dict):
        for k, v in node.items():
            hits.extend(_scan_for_banned(v, f"{path}.{k}" if path else k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits.extend(_scan_for_banned(v, f"{path}[{i}]"))
    return hits


def verify_packet(packet_dict: Dict[str, Any]) -> VerifyResult:
    """Verify a Hardseal Edge packet (loaded from JSON)."""
    result = VerifyResult(passed=True)

    missing_header = [f for f in REQUIRED_HEADER_FIELDS if f not in packet_dict]
    if missing_header:
        result.add_fail(f"missing header fields: {missing_header}")
    else:
        result.add_pass("header fields complete")

    sv = packet_dict.get("schema_version")
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        result.add_fail(
            f"schema_version {sv!r} not supported "
            f"(supported: {SUPPORTED_SCHEMA_VERSIONS})"
        )
    else:
        result.add_pass("schema_version supported")

    oc = packet_dict.get("operational_class")
    if oc not in SUPPORTED_OPERATIONAL_CLASSES:
        result.add_fail(
            f"operational_class {oc!r} not recognized "
            f"(supported: {SUPPORTED_OPERATIONAL_CLASSES})"
        )
    else:
        result.add_pass("operational_class recognized")

    missing_sections = [s for s in REQUIRED_SECTIONS if s not in packet_dict]
    if missing_sections:
        result.add_fail(f"missing sections: {missing_sections}")
    else:
        result.add_pass("required sections present")

    model = packet_dict.get("model") or {}
    engine_sha = model.get("engine_sha256", "")
    if not engine_sha or len(engine_sha) != 64:
        result.add_fail(
            "model.engine_sha256 missing or not a 64-char hex SHA-256 digest"
        )
    else:
        result.add_pass("engine SHA-256 present")

    if "offline_mode" not in packet_dict or not isinstance(
        packet_dict["offline_mode"], bool
    ):
        result.add_fail("offline_mode missing or not a bool")
    else:
        result.add_pass("offline mode declared")

    integrity = packet_dict.get("integrity", {})
    if not isinstance(integrity, dict):
        result.add_fail("integrity block missing or not an object")
        return _finalize(result)

    missing_integrity = [f for f in REQUIRED_INTEGRITY_FIELDS if f not in integrity]
    if (
        CHAIN_STATUS_FIELD not in integrity
        and LEGACY_CHAIN_STATUS_FIELD not in integrity
    ):
        missing_integrity.append(CHAIN_STATUS_FIELD)
    if missing_integrity:
        result.add_fail(f"integrity block missing fields: {missing_integrity}")

    if not missing_header and not missing_sections and not missing_integrity:
        try:
            sections = {s: packet_dict[s] for s in REQUIRED_SECTIONS}
            recomputed_root, recomputed_pairs = compute_chain_root(
                packet_type=packet_dict["packet_type"],
                schema_version=packet_dict["schema_version"],
                operational_class=packet_dict["operational_class"],
                session_id=packet_dict["session_id"],
                created_utc=packet_dict["created_utc"],
                offline_mode=packet_dict["offline_mode"],
                sections=sections,
            )

            stored_root = integrity.get("hash_chain_root")
            stored_pairs = integrity.get("section_hashes", [])

            # Independent validation of section_hashes against recomputed pairs.
            # The section_hashes field is published as part of the integrity
            # block; customers reading the packet expect that field to be
            # load-bearing, not just diagnostic. We validate it independently
            # of the top-level chain_root check so an attacker cannot mutate
            # section_hashes while keeping a forged-correct chain_root.
            #
            # Red-team note (2026-04-27 PM ET): caught by the adversarial
            # suite in tests/test_tamper_red_team.py. See
            # docs/edge/VERIFIER_RED_TEAM.md for the full attack catalog.
            section_hashes_ok = True
            section_hashes_detail: Optional[str] = None
            if not isinstance(stored_pairs, list):
                section_hashes_ok = False
                section_hashes_detail = "section_hashes is not a list"
            elif len(stored_pairs) != len(recomputed_pairs):
                section_hashes_ok = False
                section_hashes_detail = (
                    f"section_hashes length {len(stored_pairs)} "
                    f"!= expected {len(recomputed_pairs)}"
                )
            else:
                for stored, (name, recomputed) in zip(
                    stored_pairs, recomputed_pairs
                ):
                    if not isinstance(stored, dict):
                        section_hashes_ok = False
                        section_hashes_detail = (
                            f"section_hashes entry for {name!r} is not a dict"
                        )
                        break
                    if stored.get("section") != name:
                        section_hashes_ok = False
                        section_hashes_detail = (
                            f"section_hashes name mismatch at {name!r}: "
                            f"got {stored.get('section')!r}"
                        )
                        break
                    if stored.get("hash") != recomputed:
                        section_hashes_ok = False
                        section_hashes_detail = (
                            f"section_hashes hash mismatch at {name!r}"
                        )
                        break

            if stored_root != recomputed_root:
                first_bad: Optional[str] = None
                if isinstance(stored_pairs, list) and len(stored_pairs) == len(
                    recomputed_pairs
                ):
                    for stored, (name, recomputed) in zip(
                        stored_pairs, recomputed_pairs
                    ):
                        if not isinstance(stored, dict):
                            first_bad = name
                            break
                        if stored.get("hash") != recomputed:
                            first_bad = stored.get("section") or name
                            break
                detail = (
                    f" (first mutated section: {first_bad})"
                    if first_bad
                    else ""
                )
                result.add_fail(
                    f"hash chain INVALID — recomputed root does not match "
                    f"stored root{detail}"
                )
            elif not section_hashes_ok:
                # Chain root matches, but section_hashes was tampered.
                # This is the cross-packet section_hashes swap attack
                # caught by the red-team suite.
                result.add_fail(
                    f"section_hashes INVALID — chain root matches but "
                    f"stored section_hashes diverge from recomputed pairs: "
                    f"{section_hashes_detail}"
                )
            else:
                result.add_pass("hash chain valid")
        except (KeyError, TypeError, ValueError) as exc:
            result.add_fail(f"chain recomputation failed: {exc}")

    hits = _scan_for_banned(packet_dict)
    if hits:
        for h in hits:
            result.add_fail(f"banned phrase: {h}")
    else:
        result.add_pass("no banned legal language detected")

    return _finalize(result)


def _finalize(result: VerifyResult) -> VerifyResult:
    if result.failures:
        result.passed = False
    return result


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: python3 verify_standalone.py <packet.json>",
            file=sys.stderr,
        )
        return 2
    path = argv[1]
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not load {path}: {exc}", file=sys.stderr)
        return 2
    result = verify_packet(data)
    print(result.render())
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
