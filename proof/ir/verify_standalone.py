#!/usr/bin/env python3
"""Hardseal Core — single-file standalone verifier.

A self-contained copy of the manifest + Layer-1 chain + Layer-2 chain +
HMAC integrity checks from `hardseal/cli.py:cmd_verify`, combined into
one file. Distributable to customers, auditors, and acquirers who want
to verify a Hardseal Core CMMC L2 readiness pack WITHOUT installing
the Hardseal codebase.

Usage:
    python3 verify_standalone.py <path-to-package-dir>

Exit codes:
    0 — package PASSes verification
    1 — package FAILs verification
    2 — usage error or unreadable file

Stdlib-only Python 3.8+. No `pip install`. No network calls. No SaaS.
This file is the entire trust surface; read it before running it.

The canonical implementation lives at:
  - `hardseal/cli.py:cmd_verify` (orchestration)
  - `hardseal/core/manifest.py:verify_manifest` (manifest checksum layer)
  - `hardseal/core/hash_chain.py` (Layer 1: 7-section package chain)
  - `hardseal/core/hashchain.py` (Layer 2: evidence-bundle artifact chain)
  - `hardseal/core/signing.py:IntegrityEngine.verify_bundle` (HMAC tag)
in the Hardseal repository. This standalone copy is intentionally
byte-equivalent in behavior — pointed at the same package, both
produce the same per-layer verdicts and the same overall PASS/FAIL.

Hardseal Core schema v1.0 / operational class cmmc-readiness-pack.
The output strings match the canonical CLI verbatim, so any tooling
that scans for `manifest OK`, `chain intact` / `... OK (N links)`, or
`HMAC OK` keeps working unchanged.

Strict modern-manifest gate (2026-05-21): if `manifest.sha256` is
missing and any modern-package marker is present
(`chain_metadata.json`, `manifest.sha256.sig`,
`evidence/evidence-bundle.json`, `evidence/evidence-bundle.json.sig`,
`verify/HOW_TO_VERIFY.md`), verification FAILS — the manifest layer
is not optional on a modern package, regardless of the legacy
"skip silently" tolerance branch for bare directories.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------------------------------------------------
# Layer 1 chain constants (mirrors hardseal/core/hash_chain.py)
# ----------------------------------------------------------------------

CORE_GENESIS_LABEL = "HARDSEAL_CORE_GENESIS_v1"

CORE_SECTION_ORDER: Tuple[str, ...] = (
    "header",
    "ssp",
    "poam",
    "evidence_index",
    "evidence_bundle",
    "oscal_assessment",
    "manifest",
)

# Files excluded from the chain's "manifest section" content-hash dict.
# Same exclusion contract as hardseal/core/hash_chain.py.
CHAIN_MANIFEST_SECTION_EXCLUDED_RELS = (
    "manifest.sha256",
    "evidence/chain_metadata.json",
)


# ----------------------------------------------------------------------
# Layer 2 chain constants (mirrors hardseal/core/hashchain.py)
# ----------------------------------------------------------------------

GENESIS_HASH = hashlib.sha256(b"HARDSEAL_GENESIS").hexdigest()


# ----------------------------------------------------------------------
# Modern-package markers (any one of these flips the verifier into
# strict mode, where a missing manifest.sha256 is a hard FAIL)
# ----------------------------------------------------------------------

MODERN_MARKERS = (
    "chain_metadata.json",
    "manifest.sha256.sig",
    os.path.join("evidence", "evidence-bundle.json"),
    os.path.join("evidence", "evidence-bundle.json.sig"),
    os.path.join("verify", "HOW_TO_VERIFY.md"),
)


# ----------------------------------------------------------------------
# canonical_json — deterministic UTF-8 JSON encoding for hashing
# ----------------------------------------------------------------------

def canonical_json(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


# ----------------------------------------------------------------------
# Manifest layer — SHA-256 checksum of every listed file
# ----------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(package_dir: str, manifest_path: str) -> Dict[str, Any]:
    """Walk manifest.sha256, recompute each file's SHA-256, compare."""
    errors: List[str] = []
    verified = 0
    with open(manifest_path, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            errors.append(f"Malformed line: {line}")
            continue
        expected_hash, rel_path = parts
        fpath = os.path.join(package_dir, rel_path)
        if not os.path.exists(fpath):
            errors.append(f"Missing file: {rel_path}")
            continue
        actual_hash = _sha256_file(fpath)
        if actual_hash != expected_hash:
            errors.append(
                f"Hash mismatch: {rel_path} "
                f"(expected {expected_hash[:16]}..., "
                f"got {actual_hash[:16]}...)"
            )
        else:
            verified += 1
    return {
        "valid": len(errors) == 0,
        "verified": verified,
        "total": len(lines),
        "errors": errors,
    }


# ----------------------------------------------------------------------
# Layer 1 chain — 7-section package chain over canonical-JSON sections.
# Conditional: runs only when evidence/chain_metadata.json is present.
# ----------------------------------------------------------------------

def _compute_manifest_section_dict(
    package_dir: str,
    excluded_rels: Tuple[str, ...] = CHAIN_MANIFEST_SECTION_EXCLUDED_RELS,
) -> Dict[str, str]:
    result: Dict[str, str] = {}
    excluded = set(excluded_rels)
    for root, _dirs, files in os.walk(package_dir):
        for fname in sorted(files):
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, package_dir)
            if rel in excluded:
                continue
            if fname.endswith(".sig"):
                continue
            result[rel] = _sha256_file(full)
    return result


def _compute_seed(
    packet_type: str,
    schema_version: str,
    operational_class: str,
    session_id: str,
    created_utc: str,
    offline_mode: bool,
    genesis_label: str,
) -> str:
    parts = [
        genesis_label,
        packet_type,
        schema_version,
        operational_class,
        session_id,
        created_utc,
        str(offline_mode).lower(),
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


def _compute_section_hashes(
    seed: str,
    sections: Dict[str, Any],
    section_order: Tuple[str, ...],
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    prev = seed
    for name in section_order:
        if name not in sections:
            raise KeyError(
                f"hash chain missing required section: {name!r}. "
                f"Required sections: {section_order}"
            )
        section_bytes = canonical_json(sections[name])
        chain_input = section_bytes + prev.encode("utf-8")
        h = hashlib.sha256(chain_input).hexdigest()
        out.append((name, h))
        prev = h
    return out


def verify_chain_from_package(package_dir: str) -> Dict[str, Any]:
    """Recompute Layer-1 chain from package contents; compare to recorded."""
    chain_metadata_path = os.path.join(
        package_dir, "evidence", "chain_metadata.json",
    )
    if not os.path.exists(chain_metadata_path):
        raise FileNotFoundError(
            f"chain_metadata.json not found at {chain_metadata_path}"
        )
    with open(chain_metadata_path, "r", encoding="utf-8") as f:
        recorded = json.load(f)

    recorded_root = recorded["chain_root_hex"]
    recorded_section_hashes = recorded["section_hashes"]
    header = recorded["header"]
    genesis_label = recorded.get("genesis_label", CORE_GENESIS_LABEL)
    section_order = tuple(recorded.get("section_order", CORE_SECTION_ORDER))

    ssp_path = os.path.join(package_dir, "assessment", "SSP.json")
    with open(ssp_path, "r", encoding="utf-8") as f:
        ssp = json.load(f)
    evidence_bundle_path = os.path.join(
        package_dir, "evidence", "evidence-bundle.json",
    )
    with open(evidence_bundle_path, "r", encoding="utf-8") as f:
        evidence_bundle = json.load(f)

    poam = recorded["poam_canonical"]
    evidence_index = recorded["evidence_index_canonical"]
    oscal_assessment = recorded.get("oscal_assessment_canonical", {})

    sections = {
        "header": header,
        "ssp": ssp,
        "poam": poam,
        "evidence_index": evidence_index,
        "evidence_bundle": evidence_bundle,
        "oscal_assessment": oscal_assessment,
        "manifest": _compute_manifest_section_dict(package_dir),
    }

    seed = _compute_seed(
        packet_type=header["packet_type"],
        schema_version=header["schema_version"],
        operational_class=header["operational_class"],
        session_id=header["session_id"],
        created_utc=header["created_utc"],
        offline_mode=header["offline_mode"],
        genesis_label=genesis_label,
    )
    recomputed_section_hashes = _compute_section_hashes(
        seed, sections, section_order,
    )
    recomputed_root = recomputed_section_hashes[-1][1]

    errors: List[str] = []
    recomputed_map = {name: h for name, h in recomputed_section_hashes}
    for entry in recorded_section_hashes:
        name = entry["name"]
        recorded_hash = entry["hash"]
        recomputed_hash = recomputed_map.get(name)
        if recomputed_hash is None:
            errors.append(
                f"chain layer: section {name!r} recorded but not recomputed"
            )
        elif recomputed_hash != recorded_hash:
            errors.append(
                f"chain layer mismatch at section {name!r} "
                f"(recorded {recorded_hash[:16]}..., "
                f"recomputed {recomputed_hash[:16]}...)"
            )

    if recomputed_root != recorded_root:
        errors.append(
            f"chain root mismatch — recorded does not match recomputed "
            f"(recorded {recorded_root[:16]}..., "
            f"recomputed {recomputed_root[:16]}...)"
        )

    return {
        "valid": len(errors) == 0,
        "chain_root": recomputed_root,
        "recorded_chain_root": recorded_root,
        "errors": errors,
    }


# ----------------------------------------------------------------------
# Layer 2 chain — evidence-bundle artifact-by-artifact chain
# ----------------------------------------------------------------------

# Mirror hardseal/core/artifact.py:canonical_bytes() — excludes THREE
# fields (artifact_hash, previous_hash, content_hash) and uses Python's
# DEFAULT separators in json.dumps (i.e., `, ` and `: `, not compact).
_ARTIFACT_NON_CHAIN_FIELDS = frozenset({
    "artifact_hash", "previous_hash", "content_hash",
})


def _artifact_canonical_hash(artifact: Dict[str, Any]) -> str:
    """SHA-256 of artifact's canonical JSON (excluding chain fields).

    Byte-equivalent to ``EvidenceArtifact.compute_hash()`` in
    ``hardseal/core/artifact.py``: ``json.dumps(d, sort_keys=True,
    ensure_ascii=True)`` (no ``separators=``, default ``, `` and ``: ``).
    """
    payload = {k: v for k, v in artifact.items()
               if k not in _ARTIFACT_NON_CHAIN_FIELDS}
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_layer2_chain(artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Walk evidence-bundle artifacts; verify previous_hash + artifact_hash."""
    if not artifacts:
        return {"valid": True, "errors": [], "links_verified": 0}
    errors: List[str] = []
    expected_prev = GENESIS_HASH
    links_verified = 0
    for i, artifact in enumerate(artifacts):
        if artifact.get("previous_hash") != expected_prev:
            errors.append(
                f"Link {i}: previous_hash mismatch "
                f"(expected {expected_prev[:16]}..., "
                f"got {(artifact.get('previous_hash') or '')[:16]}...)"
            )
        canonical_hash = _artifact_canonical_hash(artifact)
        expected_current = hashlib.sha256(
            f"{expected_prev}:{canonical_hash}".encode("utf-8")
        ).hexdigest()
        if artifact.get("artifact_hash") != expected_current:
            errors.append(
                f"Link {i}: artifact_hash mismatch "
                f"(expected {expected_current[:16]}..., "
                f"got {(artifact.get('artifact_hash') or '')[:16]}...)"
            )
        expected_prev = artifact.get("artifact_hash", "")
        if not errors or len(errors) <= i:
            links_verified += 1
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "links_verified": links_verified if not errors else 0,
    }


# ----------------------------------------------------------------------
# HMAC integrity tag (mirrors SigningEngine.verify_bundle)
# ----------------------------------------------------------------------

def _find_hmac_secret(package_dir: str) -> Optional[bytes]:
    """Look for an HMAC secret INSIDE the package itself.

    This standalone verifier is designed for offline third-party
    verification. Customer-shipped packs do NOT include the secret
    (it would defeat HMAC's symmetric-trust guarantee). When no secret
    is found in-package, the caller prints SKIPPED — same disposition
    as the canonical CLI's `keys_exist()`-false branch.

    For build-side self-verification with workspace access, use the
    canonical `python3 -m hardseal verify --package <dir>` instead.
    """
    in_package = os.path.join(package_dir, "keys", "hardseal.key")
    if os.path.isfile(in_package):
        with open(in_package, "rb") as fp:
            return fp.read()
    return None


def verify_hmac_tag(
    bundle_dict: Dict[str, Any],
    hmac_hex: str,
    secret: bytes,
) -> bool:
    """Mirror SigningEngine.verify_bundle: HMAC-SHA256 over canonical bundle.

    Excludes `signature` and `signer_public_key`. Note: matches the
    canonical implementation's choice of NOT passing `separators=` to
    json.dumps — it uses Python's default `, ` and `: ` separators
    (intentional, for byte-equivalence with hardseal/core/signing.py).
    """
    to_verify = {k: v for k, v in bundle_dict.items()
                 if k not in ("signature", "signer_public_key")}
    canonical = json.dumps(
        to_verify, sort_keys=True, ensure_ascii=True,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).digest()
    expected = _hmac.new(secret, digest, hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, hmac_hex or "")


# ----------------------------------------------------------------------
# Orchestrator — mirrors hardseal/cli.py:cmd_verify output exactly
# ----------------------------------------------------------------------

def verify_package(target_dir: str) -> bool:
    """Run all applicable verification layers; return True on PASS."""
    if not os.path.isdir(target_dir):
        print(f"[!] Package not found: {target_dir}", file=sys.stderr)
        return False

    print(f"[*] Verifying: {target_dir}")
    all_ok = True

    # 1. Layer 1 chain (conditional)
    chain_metadata_path = os.path.join(
        target_dir, "evidence", "chain_metadata.json",
    )
    if os.path.exists(chain_metadata_path):
        print("[*] Verifying Layer 1 hash-chain...", end=" ")
        try:
            chain_result = verify_chain_from_package(target_dir)
            if chain_result["valid"]:
                print(
                    f"OK (chain_root {chain_result['chain_root'][:16]}...)"
                )
            else:
                print("FAILED")
                for err in chain_result["errors"]:
                    print(f"    - {err}")
                all_ok = False
        except Exception as e:
            print("FAILED")
            print(f"    - chain layer raised {type(e).__name__}: {e}")
            print("    - (a section file may be corrupt or unparseable)")
            all_ok = False

    # 2. Manifest layer (with strict modern-marker gate)
    manifest_path = os.path.join(target_dir, "manifest.sha256")
    if os.path.exists(manifest_path):
        print("[*] Verifying manifest checksums...", end=" ")
        m_result = verify_manifest(target_dir, manifest_path)
        if m_result["valid"]:
            print(f"OK ({m_result['verified']}/{m_result['total']} files)")
        else:
            print("FAILED")
            for err in m_result["errors"]:
                print(f"    - {err}")
            all_ok = False
    else:
        present_markers = [
            rel for rel in MODERN_MARKERS
            if os.path.exists(os.path.join(target_dir, rel))
        ]
        if present_markers:
            print(
                "[!] ERROR [verify:manifest_missing] manifest.sha256 is "
                "required for modern Hardseal packages"
            )
            print(
                f"    - modern package markers present: "
                f"{', '.join(present_markers)}"
            )
            print(
                "    - a modern package missing manifest.sha256 is tampering "
                "or corruption, not a legacy tolerance condition"
            )
            all_ok = False
        else:
            print("[*] No manifest.sha256 found, skipping manifest check.")

    # 3. Layer 2 chain over evidence-bundle artifacts
    evidence_bundle_path = os.path.join(
        target_dir, "evidence", "evidence-bundle.json",
    )
    bundle: Optional[Dict[str, Any]] = None
    if os.path.exists(evidence_bundle_path):
        try:
            with open(evidence_bundle_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(
                "[*] Verifying hash chain... FAILED"
            )
            print(f"    - could not load evidence-bundle.json: {exc}")
            all_ok = False

    if bundle is not None:
        print("[*] Verifying hash chain...", end=" ")
        artifacts = bundle.get("artifacts", [])
        l2_result = verify_layer2_chain(artifacts)
        if l2_result["valid"]:
            print(f"OK ({l2_result['links_verified']} links)")
        else:
            print("FAILED")
            for err in l2_result["errors"]:
                print(f"    - {err}")
            all_ok = False

        # 4. HMAC integrity tag (conditional on a signature being present)
        signature_hex = bundle.get("signature")
        if signature_hex:
            print("[*] Verifying HMAC integrity tag...", end=" ")
            secret = _find_hmac_secret(target_dir)
            if secret is None:
                print("SKIPPED (no HMAC secret found)")
            else:
                sig_valid = verify_hmac_tag(bundle, signature_hex, secret)
                if sig_valid:
                    key_id = (bundle.get("signer_public_key") or "")[:8]
                    print(f"OK (key: {key_id}...)")
                else:
                    print("FAILED")
                    all_ok = False
        else:
            print("[*] No integrity tag present on bundle.")
    elif not os.path.exists(evidence_bundle_path):
        print("[*] No bundle data found for chain verification.")

    print("")
    if all_ok:
        print("[+] VERIFICATION PASSED -- bundle integrity confirmed.")
    else:
        print("[!] VERIFICATION FAILED -- evidence may be tampered.")
    return all_ok


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: python3 verify_standalone.py <path-to-package-dir>",
            file=sys.stderr,
        )
        return 2
    return 0 if verify_package(argv[1]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
