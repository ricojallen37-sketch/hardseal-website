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

# Receipt JSON content kept tiny. The proof check only checks SHA-256 vs
# sidecar, but the schema-language check still requires the public integrity
# field name.
SAMPLE_RECEIPT_JSON = (
    b'{"integrity":{"chain_verification_status":"matches_recomputed_chain"},'
    b'"packet_type":"test","schema_version":"1.0"}\n'
)


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
        rg.check_receipt_schema_language(self.root, result)
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

    def test_verifier_nonzero_exit_caught(self) -> None:
        # Replace the stub verifier with one that prints PASS but exits
        # non-zero. The strict contract requires returncode == 0.
        (self.root / "downloads" / "verify_standalone.py").write_text(
            "import sys\nprint('result: PASS')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        result = rg.GateResult()
        rg.check_proof_artifacts(self.root, result)
        self.assertFails(result, "returncode=1")

    def test_verifier_sub_fail_line_caught(self) -> None:
        # PASS summary but a sub-check failure should be caught.
        (self.root / "downloads" / "verify_standalone.py").write_text(
            "print('  FAIL: chain root mismatch')\nprint('result: PASS')\n",
            encoding="utf-8",
        )
        result = rg.GateResult()
        rg.check_proof_artifacts(self.root, result)
        self.assertFails(result, "sub-check 'FAIL:'")

    def test_sidecar_wrong_filename_token_caught(self) -> None:
        # Sidecar names a different file than its own basename.
        receipt = self.root / rg.PUBLIC_RECEIPTS[0]
        sidecar = receipt.with_suffix(receipt.suffix + ".sha256")
        # Use the correct digest but point at the wrong filename.
        import hashlib as _hashlib
        digest = _hashlib.sha256(receipt.read_bytes()).hexdigest()
        sidecar.write_text(f"{digest}  wrong-file.json\n", encoding="utf-8")
        result = rg.GateResult()
        rg.check_links(self.root, result)
        self.assertFails(result, "wrong file")


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

    def test_ledger_label_in_footer_only(self) -> None:
        # A correct label OUTSIDE the trust-ledger block does not save
        # a mislabeled block. Reviewer-requested scoping check.
        v = self.root / "verify.html"
        v.write_text(textwrap.dedent("""\
            <!doctype html><html><body>
            <footer>Receipts #1-#4 · Index — see below</footer>
            <div id="trust-ledger">
              <div class="qs-title">▸ Hardseal Trust Ledger — Receipt #5</div>
              <p>Receipt #2 mapping: AU.L2-3.3.1 / AU.L2-3.3.2 / AU.L2-3.3.8.</p>
            </div>
            </body></html>
            """), encoding="utf-8")
        result = rg.GateResult()
        rg.check_trust_ledger(self.root, result)
        # Both failure modes should fire: missing label inside block,
        # and Receipt #5 inside block.
        self.assertFails(result, "not labeled")
        self.assertFails(result, "Receipt #5")

    def test_ledger_block_missing(self) -> None:
        # If the <... id="trust-ledger"> element is gone entirely, the
        # check must fail explicitly rather than silently pass.
        v = self.root / "verify.html"
        v.write_text(
            '<!doctype html><html><body><p>Some other content.</p></body></html>',
            encoding="utf-8",
        )
        result = rg.GateResult()
        rg.check_trust_ledger(self.root, result)
        self.assertFails(result, "trust-ledger")


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

    def test_non_script_banned_phrase_array_is_NOT_allowed(self) -> None:
        # Without <script> wrapping, a quoted-string list in body text
        # must NOT be a free pass. Previously a structural heuristic
        # allowed any line of comma-separated quoted strings; that was
        # exploitable.
        self._write_page(
            '<p>Marketing copy: "we certify","certified compliant",'
            '"endorsed by cyber ab".</p>'
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertTrue(
            any("certified" in f for f in result.failures),
            msg=(
                "Quoted-string list outside <script> must be flagged; "
                f"got {result.failures}"
            ),
        )

    # --- Reviewer-supplied exploits (must FAIL the gate) -----------------

    def test_reviewer_exploit_certified_with_sample_in_next_sentence(self) -> None:
        # 'Hardseal Edge is certified for CMMC. (sample text follows.)'
        # The hedge 'sample' is in a DIFFERENT sentence; it must not
        # exempt 'certified'.
        self._write_page(
            "<p>Hardseal Edge is certified for CMMC. (sample text follows.)</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertTrue(
            any("certified" in f for f in result.failures),
            msg=(
                "Reviewer exploit (certified + sample in next sentence) must "
                f"FAIL; got passes={result.passes}, failures={result.failures}"
            ),
        )

    def test_reviewer_exploit_certified_with_demo_in_next_sentence(self) -> None:
        # 'Hardseal is certified. The next section is a demo replay.'
        self._write_page(
            "<p>Hardseal is certified. The next section is a demo replay.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertTrue(
            any("certified" in f for f in result.failures),
            msg=(
                "Reviewer exploit (certified + demo in next sentence) must "
                f"FAIL; got {result.failures}"
            ),
        )

    def test_reviewer_exploit_customer_enclave_no_possessive(self) -> None:
        # 'Hardseal runs in a customer enclave.' — generic "customer
        # enclave" without possessive must NOT exempt enclave.
        self._write_page(
            "<p>Hardseal runs in a customer enclave.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertTrue(
            any("enclave" in f for f in result.failures),
            msg=(
                "Reviewer exploit (Hardseal runs in a customer enclave) must "
                f"FAIL; got {result.failures}"
            ),
        )

    def test_possessive_customer_enclave_is_allowed(self) -> None:
        # Conversely, the real DPA wording with possessive must pass.
        self._write_page(
            "<p>Conduct CUI handling on Customer's enclave or in a "
            "documented secure environment under Customer's direction.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=f"Possessive Customer's enclave should pass; got {result.failures}",
        )

    def test_ed25519_roadmap_qualified_is_allowed(self) -> None:
        # Real edge.html wording.
        self._write_page(
            "<p>That is what the operator-held signing secret "
            "(and the Ed25519 signature on the roadmap) is for.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=f"Roadmap-qualified Ed25519 should pass; got {result.failures}",
        )

    def test_detection_signature_research_term_is_allowed(self) -> None:
        # The research field report uses 'signature' to mean a
        # detection rule. Must not be flagged as an overclaim.
        self._write_page(
            "<p>It catalogs twelve attack patterns observed across "
            "pre-assessment packets, ships detection signatures for "
            "seven of them, and documents the remaining five with "
            "signature-only material.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=(
                "Research detection-signature usage should pass; "
                f"got {result.failures}"
            ),
        )

    def test_hmac_sha256_signature_is_allowed(self) -> None:
        # Real proof_IR wording.
        self._write_page(
            "<p>Package-level SHA-256 manifest with detached "
            "HMAC-SHA256 signature file.</p>"
        )
        result = rg.GateResult()
        rg.check_overclaim_firewall(self.root, result)
        self.assertEqual(
            result.failures, [],
            msg=f"HMAC-SHA256 signature should pass; got {result.failures}",
        )


class TestReceiptSchemaLanguage(GateTestBase):
    """Public receipt JSON must stay chain-scoped and avoid retired wording."""

    def test_retired_integrity_field_fails(self) -> None:
        receipt = self.root / rg.PUBLIC_RECEIPTS[0]
        receipt.write_text(
            json.dumps(
                {
                    "packet_type": "test",
                    "schema_version": "1.0",
                    "integrity": {"tamper_" + "status": "clean"},
                }
            ),
            encoding="utf-8",
        )
        _write_sidecar(receipt)

        result = rg.GateResult()
        rg.check_receipt_schema_language(self.root, result)
        self.assertFails(result, "retired integrity field")

    def test_public_receipt_overclaim_phrase_fails(self) -> None:
        receipt = self.root / rg.PUBLIC_RECEIPTS[1]
        receipt.write_text(
            json.dumps(
                {
                    "packet_type": "test",
                    "schema_version": "1.0",
                    "integrity": {
                        "chain_verification_status": "matches_recomputed_chain"
                    },
                    "limitations": ["tamper-evident evidence only"],
                }
            ),
            encoding="utf-8",
        )
        _write_sidecar(receipt)

        result = rg.GateResult()
        rg.check_receipt_schema_language(self.root, result)
        self.assertFails(result, "unsupported phrase")


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
