"""Native CMMC packet QA receipt builder and verifier.

This module seals one pre-review packet finding into a deterministic
SHA-256 chain. It proves the finding record still matches the anchored
receipt. It does not prove compliance, customer facts, or review outcome.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


GENESIS_LABEL = "HARDSEAL_CMMC_PACKET_QA_RECEIPT_v1"
RECEIPT_TYPE = "hardseal_cmmc_packet_qa_receipt"
SCHEMA_VERSION = "0.1"
HASH_ALGORITHM = "sha256_canonical_json_chain_v1"

SECTION_ORDER: Tuple[str, ...] = (
    "metadata",
    "framework_basis",
    "packet_slice",
    "packet_claim",
    "evidence_observed",
    "finding",
    "reviewer_question",
    "next_proof_needed",
    "limitations",
)

REQUIRED_TOP_LEVEL_FIELDS = (
    "receipt_type",
    "schema_version",
    "receipt_id",
    "created_utc",
    "offline_mode",
    "sections",
    "integrity",
)

REQUIRED_INTEGRITY_FIELDS = (
    "hash_chain_algorithm",
    "genesis_label",
    "section_order",
    "section_hashes",
    "chain_root",
    "tamper_status",
    "verification_command",
)

BANNED_PHRASES = (
    "we certify",
    "hardseal certifies",
    "hardseal assesses",
    "certified compliant",
    "compliance-equivalent",
    "assessor-equivalent",
    "equivalent to a c3pao",
    "endorsed by cyber ab",
    "guaranteed pass",
    "guaranteed compliant",
    "accepted by c3pao",
    "assessor-ready",
)


@dataclass
class ReceiptVerifyResult:
    """Operator-readable verification result."""

    passed: bool = False
    checks_passed: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    chain_root: Optional[str] = None

    def add_pass(self, name: str) -> None:
        self.checks_passed.append(name)

    def add_fail(self, msg: str) -> None:
        self.passed = False
        self.failures.append(msg)

    def render(self) -> str:
        lines: List[str] = []
        for check in self.checks_passed:
            lines.append(f"  PASS: {check}")
        for failure in self.failures:
            lines.append(f"  FAIL: {failure}")
        if self.chain_root:
            lines.append("")
            lines.append(f"chain_root: {self.chain_root}")
        lines.append("")
        lines.append(f"result: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


def canonical_json(obj: Any) -> bytes:
    """Return deterministic JSON bytes for hashing."""

    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seed(receipt: Dict[str, Any]) -> str:
    seed_payload = {
        "genesis_label": GENESIS_LABEL,
        "receipt_type": receipt["receipt_type"],
        "schema_version": receipt["schema_version"],
        "receipt_id": receipt["receipt_id"],
        "created_utc": receipt["created_utc"],
        "offline_mode": receipt["offline_mode"],
    }
    return hashlib.sha256(canonical_json(seed_payload)).hexdigest()


def compute_section_hashes(
    receipt: Dict[str, Any],
) -> Tuple[str, List[Dict[str, str]]]:
    """Compute the receipt chain root and per-section hashes."""

    sections = receipt["sections"]
    previous = _seed(receipt)
    section_hashes: List[Dict[str, str]] = []

    for section in SECTION_ORDER:
        if section not in sections:
            raise KeyError(f"missing receipt section: {section}")
        payload = {
            "section": section,
            "payload": sections[section],
            "previous_hash": previous,
        }
        current = hashlib.sha256(canonical_json(payload)).hexdigest()
        section_hashes.append({"section": section, "hash": current})
        previous = current

    return previous, section_hashes


def seal_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of receipt with recomputed integrity fields."""

    sealed = copy.deepcopy(receipt)
    chain_root, section_hashes = compute_section_hashes(sealed)
    sealed["integrity"] = {
        "hash_chain_algorithm": HASH_ALGORITHM,
        "genesis_label": GENESIS_LABEL,
        "section_order": list(SECTION_ORDER),
        "section_hashes": section_hashes,
        "chain_root": chain_root,
        "tamper_status": "clean",
        "verification_command": (
            "python3 -m hardseal.receipts.cmmc_packet_qa verify <receipt.json>"
        ),
    }
    return sealed


def build_receipt(
    *,
    receipt_id: str,
    created_utc: str,
    sections: Dict[str, Any],
    offline_mode: bool = True,
) -> Dict[str, Any]:
    """Build and seal a native CMMC packet QA receipt."""

    receipt = {
        "receipt_type": RECEIPT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "created_utc": created_utc,
        "offline_mode": offline_mode,
        "sections": copy.deepcopy(sections),
        "integrity": {},
    }
    return seal_receipt(receipt)


def sample_ia_l2_3_5_3_receipt() -> Dict[str, Any]:
    """Return the first CMMC packet QA sample receipt."""

    sections = {
        "metadata": {
            "operator": "Rico Allen",
            "organization": "Hardseal LLC",
            "receipt_name": "Receipt 001 - CMMC Packet QA - IA.L2-3.5.3",
            "input_class": "synthetic_public_sample",
            "customer_data_rule": (
                "No CUI, credentials, screenshots, network maps, data-flow "
                "diagrams, SSPs, or sensitive customer evidence are included."
            ),
        },
        "framework_basis": {
            "framework": "CMMC Level 2 / NIST SP 800-171 Rev. 2",
            "source": "NIST SP 800-171A assessment procedures CSV",
            "source_url": (
                "https://csrc.nist.gov/files/pubs/sp/800/171/a/final/docs/"
                "sp800-171a-assessment-procedures.csv"
            ),
            "control": {
                "id": "IA.L2-3.5.3",
                "nist_sp_800_171": "3.5.3",
                "requirement": "Use multifactor authentication.",
            },
            "assessment_objectives": [
                {
                    "id": "3.5.3[a]",
                    "text": "privileged accounts are identified.",
                },
                {
                    "id": "3.5.3[b]",
                    "text": (
                        "multifactor authentication is implemented for local "
                        "access to privileged accounts."
                    ),
                },
                {
                    "id": "3.5.3[c]",
                    "text": (
                        "multifactor authentication is implemented for network "
                        "access to privileged accounts."
                    ),
                },
                {
                    "id": "3.5.3[d]",
                    "text": (
                        "multifactor authentication is implemented for network "
                        "access to non-privileged accounts."
                    ),
                },
            ],
        },
        "packet_slice": {
            "contractor_profile": "Cardinal Point Aerostructures synthetic sample",
            "artifact_area": "identity and access evidence",
            "packet_scope": "single objective-sliced sample finding",
            "safe_input_summary": [
                "SSP excerpt claims MFA is enforced for all remote and privileged access.",
                "Policy excerpt states privileged access requires MFA.",
                "Synthetic admin-account export lists privileged accounts and MFA status.",
            ],
        },
        "packet_claim": {
            "claim_id": "CLAIM-IA-3-5-3-MFA-001",
            "claim_text": (
                "The packet claims MFA is implemented for local privileged "
                "access, network privileged access, and network non-privileged "
                "access."
            ),
            "claimed_objective_coverage": [
                "3.5.3[a]",
                "3.5.3[b]",
                "3.5.3[c]",
                "3.5.3[d]",
            ],
        },
        "evidence_observed": {
            "observed_items": [
                {
                    "artifact": "admin-account-export.csv",
                    "observation": (
                        "Privileged accounts are listed, including break-glass "
                        "and service-admin accounts."
                    ),
                    "supports": ["3.5.3[a]"],
                },
                {
                    "artifact": "conditional-access-policy-summary.md",
                    "observation": (
                        "MFA policy is described for cloud network sign-in, "
                        "but no local console or local admin path evidence is present."
                    ),
                    "supports": ["3.5.3[c]", "3.5.3[d]"],
                    "does_not_support": ["3.5.3[b]"],
                },
                {
                    "artifact": "vpn-auth-screenshot-redacted.txt",
                    "observation": (
                        "Network access evidence shows MFA prompt text, but no "
                        "sample authentication log is included."
                    ),
                    "supports": ["3.5.3[c]"],
                    "partial_support": ["3.5.3[d]"],
                },
            ],
        },
        "finding": {
            "finding_id": "HS-CMMC-QA-2026-001",
            "status": "partially_supported",
            "severity": "medium",
            "unsupported_objectives": ["3.5.3[b]"],
            "partially_supported_objectives": ["3.5.3[d]"],
            "supported_objectives": ["3.5.3[a]", "3.5.3[c]"],
            "finding_text": (
                "The packet names privileged accounts and shows some network "
                "MFA evidence, but it does not yet support the SSP claim that "
                "MFA is implemented for local access to privileged accounts."
            ),
            "why_it_matters": (
                "A reviewer can ask for objective-level evidence, not just a "
                "general MFA policy statement."
            ),
        },
        "reviewer_question": {
            "question": (
                "Where is the objective-level evidence that local privileged "
                "account access requires MFA?"
            ),
            "expected_answer_shape": (
                "A local admin login control export, PAM configuration, or "
                "equivalent record mapped directly to 3.5.3[b]."
            ),
        },
        "next_proof_needed": {
            "primary_next_artifact": "local-privileged-mfa-control-export",
            "acceptable_examples": [
                "PAM policy export showing local privileged MFA enforcement",
                "Endpoint or directory policy showing local admin MFA control",
                "Procedure plus test record showing local privileged MFA behavior",
            ],
            "do_not_collect_here": [
                "CUI",
                "credentials",
                "unredacted network maps",
                "full SSP",
                "sensitive screenshots",
            ],
        },
        "limitations": {
            "what_pass_proves": [
                "The receipt sections still match the recorded SHA-256 chain root.",
                "The finding text, objective mapping, and limitations were not changed after sealing.",
            ],
            "what_pass_does_not_prove": [
                "customer facts",
                "complete evidence coverage",
                "formal review result",
                "official CMMC status",
                "physical truth",
            ],
            "claim_boundary": (
                "Hardseal records whether the packet matches the anchored "
                "finding under explicit assumptions."
            ),
        },
    }

    return build_receipt(
        receipt_id="receipt-001-cmmc-packet-qa-ia-l2-3-5-3-sample",
        created_utc="2026-06-13T18:00:00Z",
        offline_mode=True,
        sections=sections,
    )


def verify_receipt(receipt: Dict[str, Any]) -> ReceiptVerifyResult:
    """Verify a native CMMC packet QA receipt."""

    result = ReceiptVerifyResult(passed=True)

    missing_top = [field for field in REQUIRED_TOP_LEVEL_FIELDS if field not in receipt]
    if missing_top:
        result.add_fail(f"missing top-level fields: {missing_top}")
    else:
        result.add_pass("top-level fields complete")

    if receipt.get("receipt_type") != RECEIPT_TYPE:
        result.add_fail(f"unsupported receipt_type: {receipt.get('receipt_type')!r}")
    else:
        result.add_pass("receipt_type recognized")

    if receipt.get("schema_version") != SCHEMA_VERSION:
        result.add_fail(f"unsupported schema_version: {receipt.get('schema_version')!r}")
    else:
        result.add_pass("schema_version supported")

    if not isinstance(receipt.get("offline_mode"), bool):
        result.add_fail("offline_mode missing or not a bool")
    else:
        result.add_pass("offline mode declared")

    sections = receipt.get("sections", {})
    if not isinstance(sections, dict):
        result.add_fail("sections missing or not an object")
        return _finalize(result)

    section_keys = set(sections)
    required_keys = set(SECTION_ORDER)
    missing_sections = [name for name in SECTION_ORDER if name not in sections]
    extra_sections = sorted(section_keys - required_keys)
    if missing_sections:
        result.add_fail(f"missing sections: {missing_sections}")
    elif extra_sections:
        result.add_fail(f"unexpected sections: {extra_sections}")
    else:
        result.add_pass("required sections present")

    integrity = receipt.get("integrity", {})
    if not isinstance(integrity, dict):
        result.add_fail("integrity block missing or not an object")
        return _finalize(result)

    missing_integrity = [
        field for field in REQUIRED_INTEGRITY_FIELDS if field not in integrity
    ]
    if missing_integrity:
        result.add_fail(f"integrity block missing fields: {missing_integrity}")
    else:
        result.add_pass("integrity fields complete")

    if integrity.get("hash_chain_algorithm") != HASH_ALGORITHM:
        result.add_fail(
            "unsupported hash_chain_algorithm: "
            f"{integrity.get('hash_chain_algorithm')!r}"
        )
    else:
        result.add_pass("hash algorithm supported")

    if integrity.get("genesis_label") != GENESIS_LABEL:
        result.add_fail(f"unexpected genesis_label: {integrity.get('genesis_label')!r}")
    else:
        result.add_pass("genesis label recognized")

    if integrity.get("section_order") != list(SECTION_ORDER):
        result.add_fail("section_order does not match verifier contract")
    else:
        result.add_pass("section order fixed")

    if not missing_top and not missing_sections and not missing_integrity:
        try:
            chain_root, section_hashes = compute_section_hashes(receipt)
            result.chain_root = chain_root
            stored_root = integrity.get("chain_root")
            stored_hashes = integrity.get("section_hashes")

            if stored_root != chain_root:
                first_bad = _first_bad_section(stored_hashes, section_hashes)
                detail = f" first_mutated_section={first_bad}" if first_bad else ""
                result.add_fail(f"chain root mismatch.{detail}")
            elif stored_hashes != section_hashes:
                result.add_fail(
                    "section_hashes mismatch while chain_root matches"
                )
            else:
                result.add_pass("hash chain valid")
        except (KeyError, TypeError, ValueError) as exc:
            result.add_fail(f"chain recomputation failed: {exc}")

    hits = _scan_for_banned(receipt)
    if hits:
        for hit in hits:
            result.add_fail(f"banned phrase: {hit}")
    else:
        result.add_pass("no banned claim language detected")

    return _finalize(result)


def _first_bad_section(
    stored_hashes: Any,
    recomputed_hashes: List[Dict[str, str]],
) -> Optional[str]:
    if not isinstance(stored_hashes, list):
        return None
    for stored, recomputed in zip(stored_hashes, recomputed_hashes):
        if not isinstance(stored, dict):
            return recomputed["section"]
        if stored.get("section") != recomputed["section"]:
            return recomputed["section"]
        if stored.get("hash") != recomputed["hash"]:
            return recomputed["section"]
    if len(stored_hashes) != len(recomputed_hashes):
        return recomputed_hashes[min(len(stored_hashes), len(recomputed_hashes) - 1)][
            "section"
        ]
    return None


def _scan_for_banned(node: Any, path: str = "") -> List[str]:
    hits: List[str] = []
    if isinstance(node, str):
        lower = node.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lower:
                hits.append(f"{path or '<root>'}: contains banned phrase {phrase!r}")
    elif isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            hits.extend(_scan_for_banned(value, child_path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(_scan_for_banned(value, f"{path}[{index}]"))
    return hits


def _finalize(result: ReceiptVerifyResult) -> ReceiptVerifyResult:
    if result.failures:
        result.passed = False
    return result


def write_receipt(path: Path, receipt: Dict[str, Any]) -> Tuple[Path, Path]:
    """Write a canonical receipt JSON and SHA-256 sidecar."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest = file_sha256(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return path, sidecar


def load_receipt(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("receipt JSON root must be an object")
    return data


def _cmd_sample(args: argparse.Namespace) -> int:
    receipt = sample_ia_l2_3_5_3_receipt()
    out_path, sidecar = write_receipt(Path(args.out), receipt)
    print(f"wrote: {out_path}")
    print(f"sidecar: {sidecar}")
    print(f"sha256: {file_sha256(out_path)}")
    print(f"chain_root: {receipt['integrity']['chain_root']}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        receipt = load_receipt(Path(args.receipt))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: could not load receipt: {exc}", file=sys.stderr)
        return 2

    result = verify_receipt(receipt)
    print(result.render())
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m hardseal.receipts.cmmc_packet_qa",
        description="Build or verify native CMMC packet QA receipts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample", help="write the IA.L2-3.5.3 sample receipt")
    sample.add_argument("--out", required=True, help="output JSON path")
    sample.set_defaults(func=_cmd_sample)

    verify = sub.add_parser("verify", help="verify a CMMC packet QA receipt")
    verify.add_argument("receipt", help="receipt JSON path")
    verify.set_defaults(func=_cmd_verify)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
