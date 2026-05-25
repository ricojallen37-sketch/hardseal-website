#!/usr/bin/env python3
"""Negative-fixture tests for scripts/release_gate.py.

Each test builds a tiny synthetic repo in a tempdir, copies the gate under
test in, mutates one thing to be wrong, runs the gate's individual checks,
and asserts the expected failure is produced. We exercise the check
functions directly (not via subprocess) so failures are diagnosable.

Standard library only. Run:
    python3 scripts/test_release_gate.py

Exit 0 = all tests pass; non-zero = a test failed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Make the gate importable when running this file directly.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import release_gate as rg  # noqa: E402


# A minimal but valid set of fixture inputs. Each test starts from this
# baseline and mutates exactly one thing.

MINIMAL_VERIFY_HTML = """<!doctype html>
<html><body>
<div id="trust-ledger">
  <div class="qs-title">▸ HARDSEAL PUBLIC TRUST LEDGER · RECEIPTS #1-#4 · INDEX</div>
  <p>One compact index for the four public demo receipts.</p>
  <p>Receipt #2 mapping: CMMC 2.0 Level 2: AU.L2-3.3.1 / AU.L2-3.3.2 / AU.L2-3.3.8.</p>
</div>
<p>These receipts are SHA-256 / hash-chain / sidecar-verifiable artifacts and
are <strong>not</strong> Ed25519-signed production evidence, customer evidence,
or compliance proof.</p>
<a href="/downloads/verify_standalone.py">Python verifier</a>
</body></html>
"""

# Receipt JSON content kept tiny — the gate only checks SHA-256 vs sidecar,
# not packet semantics (the standalone verifier is exercised separately).
SAMPLE_RECEIPT_JSON = b'{"packet_type":"test","schema_version":"1.0"}\n'


def _write_sidecar(receipt_path: Path) -> None:
    digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    sidecar = receipt_path.with_suffix(receipt_path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {receipt_path.name}\n", encoding="utf-8")


def _build_baseline_repo(root: Path) -> None:
    """Receipts + sidecars + verify.html with a labeled Trust Ledger."""
    for name in rg.PUBLIC_RECEIPTS:
        p = root / name
        p.write_bytes(SAMPLE_RECEIPT_JSON)
        _write_sidecar(p)
    (root / "verify.html").write_text(MINIMAL_VERIFY_HTML, encoding="utf-8")
    # verify.html links the standalone verifier; the link-check expects
    # the file to exist. We create a stub — the proof-artifact check
    # would normally invoke it, but the baseline test runs the link
    # check, not the proof check (which is exercised separately above).
    downloads = root / "downloads"
    downloads.mkdir(exist_ok=True)
    # Stub verifier: always prints "result: PASS" so the proof check
    # (which exercises Receipt #1 against this) succeeds. The real
    # verifier's correctness is the verifier's own concern; the gate's
    # job is to invoke it and confirm the PASS contract.
    (downloads / "verify_standalone.py").write_text(
        "import sys\nprint('result: PASS')\n",
        encoding="utf-8",
    )


class GateTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="release_gate_test_")
        self.root = Path(self.tmp)
        _build_baseline_repo(self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assertFails(self, result: rg.GateResult, substring: str) -> None:
        joined = "\n".join(result.failures)
        self.assertTrue(
            any(substring in f for f in result.failures),
            msg=(
                f"Expected a failure containing {substring!r}.\n"
                f"Got failures:\n{joined}\n"
                f"And passes:\n" + "\n".join(result.passes)
            ),
        )

    def assertNoFailContains(self, result: rg.GateResult, substring: str) -> None:
        joined = "\n".join(result.failures)
        self.assertFalse(
            any(substring in f for f in result.failures),
            msg=f"Did not expect failure containing {substring!r}; got:\n{joined}",
        )


class TestBaselinePasses(GateTestBase):
    """Sanity: the baseline fixture should pass every check."""

    def test_baseline(self) -> None:
        result = rg.GateResult()
        rg.check_proof_artifacts(self.root, result)
        rg.check_trust_ledger(self.root, result)
        rg.check_receipt2_mapping(self.root, result)
        rg.check_overclaim_firewall(self.root, result)
        rg.check_links(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=f"Baseline failed: {result.failures}",
        )


class TestProofArtifacts(GateTestBase):
    """Bad sidecar hash must be caught."""

    def test_bad_sidecar_hash(self) -> None:
        receipt = self.root / rg.PUBLIC_RECEIPTS[1]
        sidecar = receipt.with_suffix(receipt.suffix + ".sha256")
        # Overwrite with a wrong digest (all zeros).
        sidecar.write_text(
            f"{'0' * 64}  {receipt.name}\n", encoding="utf-8",
        )
        result = rg.GateResult()
        rg.check_proof_artifacts(self.root, result)
        self.assertFails(result, "sidecar hash mismatch")
        self.assertFails(result, receipt.name)

    def test_missing_sidecar(self) -> None:
        receipt = self.root / rg.PUBLIC_RECEIPTS[2]
        receipt.with_suffix(receipt.suffix + ".sha256").unlink()
        result = rg.GateResult()
        rg.check_proof_artifacts(self.root, result)
        self.assertFails(result, "missing sidecar")


class TestTrustLedger(GateTestBase):
    """Trust Ledger labeled as Receipt #5 must be caught."""

    def test_ledger_labeled_as_receipt_5(self) -> None:
        v = self.root / "verify.html"
        text = v.read_text(encoding="utf-8")
        # Inject a Receipt #5 label inside the trust-ledger block.
        bad = text.replace(
            "RECEIPTS #1-#4 · INDEX",
            "Trust Ledger — Receipt #5",
        )
        v.write_text(bad, encoding="utf-8")
        result = rg.GateResult()
        rg.check_trust_ledger(self.root, result)
        self.assertFails(result, "Receipt #5")

    def test_ledger_label_missing(self) -> None:
        v = self.root / "verify.html"
        text = v.read_text(encoding="utf-8")
        # Strip the "Receipts #1-#4 · Index" label entirely.
        bad = text.replace("RECEIPTS #1-#4 · INDEX", "general index")
        v.write_text(bad, encoding="utf-8")
        result = rg.GateResult()
        rg.check_trust_ledger(self.root, result)
        self.assertFails(result, "not labeled")


class TestReceipt2Mapping(GateTestBase):
    """Receipt #2 broadened beyond AU.L2-3.3.{1,2,8} must be caught."""

    def test_broadened_mapping_3_3_5(self) -> None:
        v = self.root / "verify.html"
        text = v.read_text(encoding="utf-8")
        bad = text.replace(
            "AU.L2-3.3.1 / AU.L2-3.3.2 / AU.L2-3.3.8",
            "AU.L2-3.3.1 / AU.L2-3.3.2 / AU.L2-3.3.5 / AU.L2-3.3.8",
        )
        v.write_text(bad, encoding="utf-8")
        result = rg.GateResult()
        rg.check_receipt2_mapping(self.root, result)
        self.assertFails(result, "AU.L2-3.3.5")
        self.assertFails(result, "broadened")

    def test_negated_forbidden_mapping_is_ok(self) -> None:
        # If the page explicitly says "Receipt #2 does NOT claim
        # AU.L2-3.3.4", the gate should not fail.
        v = self.root / "verify.html"
        text = v.read_text(encoding="utf-8")
        injected = text.replace(
            "AU.L2-3.3.1 / AU.L2-3.3.2 / AU.L2-3.3.8.",
            "AU.L2-3.3.1 / AU.L2-3.3.2 / AU.L2-3.3.8. "
            "Receipt #2 does NOT claim AU.L2-3.3.4.",
        )
        v.write_text(injected, encoding="utf-8")
        result = rg.GateResult()
        rg.check_receipt2_mapping(self.root, result)
        self.assertNoFailContains(result, "AU.L2-3.3.4")


class TestOverclaimFirewall(GateTestBase):
    """Unsupported affirmative overclaim language must be caught."""

    def _write_page(self, body: str) -> Path:
        p = self.root / "claim_test.html"
        p.write_text(f"<!doctype html><html><body>{body}</body></html>",
                     encoding="utf-8")
        return p

    def test_unsupported_signed_claim(self) -> None:
        self._write_page(
            "<p>Hardseal Edge produces Ed25519-signed production "
            "evidence today.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        # Multiple phrases hit here (Ed25519, signed, production deployment-
        # adjacent). At minimum one of them must fail.
        self.assertTrue(
            any("Ed25519" in f or "signed" in f for f in result.failures),
            msg=f"Expected Ed25519/signed overclaim to fail; got {result.failures}",
        )

    def test_unsupported_certified_compliant(self) -> None:
        self._write_page(
            "<p>Hardseal is certified and compliant.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertTrue(
            any("certified" in f for f in result.failures),
            msg=f"Expected 'certified' overclaim to fail; got {result.failures}",
        )
        self.assertTrue(
            any("compliant" in f for f in result.failures),
            msg=f"Expected 'compliant' overclaim to fail; got {result.failures}",
        )

    def test_unsupported_tamper_evident(self) -> None:
        self._write_page(
            "<p>Hardseal packets are tamper-evident in production.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertTrue(
            any("tamper-evident" in f for f in result.failures),
            msg=f"Expected 'tamper-evident' overclaim to fail; got {result.failures}",
        )

    def test_negated_claim_is_allowed(self) -> None:
        self._write_page(
            "<p>These receipts are <strong>not</strong> Ed25519-signed "
            "production evidence, customer evidence, or compliance proof.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        # The page should still pass — negation is the allowed context.
        self.assertEqual(
            result.failures, [],
            msg=f"Negated claims should pass; got {result.failures}",
        )

    def test_signed_in_contract_context_is_allowed(self) -> None:
        self._write_page(
            "<p>This DPA becomes binding only when expressly incorporated "
            "into a signed Master Services Agreement.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=f"Contract-context 'signed' should pass; got {result.failures}",
        )

    def test_script_block_banned_phrase_array_is_allowed(self) -> None:
        self._write_page(
            '<script>const BANNED = ["we certify","certified compliant",'
            '"endorsed by cyber ab"];</script>'
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=f"Verifier banned-phrase array should pass; got {result.failures}",
        )


class TestLinks(GateTestBase):
    """Anchor and artifact link surface must be caught when missing."""

    def test_trust_ledger_anchor_missing(self) -> None:
        v = self.root / "verify.html"
        text = v.read_text(encoding="utf-8")
        v.write_text(text.replace('id="trust-ledger"', 'id="other"'),
                     encoding="utf-8")
        result = rg.GateResult()
        rg.check_links(self.root, result)
        self.assertFails(result, "#trust-ledger anchor missing")

    def test_receipt_artifact_missing(self) -> None:
        (self.root / rg.PUBLIC_RECEIPTS[3]).unlink()
        result = rg.GateResult()
        rg.check_links(self.root, result)
        self.assertFails(result, "expected public artifact missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
