#!/usr/bin/env python3
"""Hardseal release gate — required check for public-proof honesty.

Doctrine: we fly what we test, we test what we fly. This script enforces
public-proof honesty so a drifted page, receipt, sidecar, or claim does
not reach the public-deploy path. The workflow that runs this script is
intended to be a required-status-check on main; branch protection on
main is what makes it deploy-blocking. See docs/ops/RELEASE_GATE.md.

Checks (all must pass; first failure does not short-circuit so the
operator sees every issue in one run):

  1. Proof artifact: every public receipt JSON has a matching .sha256
     sidecar; recomputed SHA-256 matches; the sidecar filename token
     names the correct receipt; the standalone verifier (if present)
     returns returncode==0 + 'result: PASS' + no sub-FAIL on EVERY
     receipt, not just Receipt #1.
  2. Trust Ledger: the <... id="trust-ledger"> element exists, its
     inner HTML is labeled "Receipts #1-#4 Index" (or equivalent), and
     it does NOT mention Receipt #5 anywhere inside.
  3. Receipt #2 mapping: scoped to row-level enclosing blocks (<tr>,
     <div>, <section>, <article>) around each Receipt #2 anchor. Must
     not broaden beyond AU.L2-3.3.{1,2,8}. AU.L2-3.3.{3..7} as Receipt
     #2 mapping fails unless within ~120 chars of a negation/future
     note.
  4. Overclaim firewall: a fixed list of unsupported affirmative claim
     phrases (signed, Ed25519, certified, compliant, ...) scanned
     across all public HTML — root *.html, blog/*.html, proof/ir/*.html,
     research/**/*.html. Allowed contexts are SENTENCE-SCOPED and
     CONCEPT-SPECIFIC: negation, roadmap qualifier, contract noun
     (signed/signature only), possessive customer-owned enclave (enclave
     only), HMAC-SHA256 (signed/signature only), detection-signature
     domain term (signature only), or an explicit OVERCLAIM_ALLOWLIST
     entry. <script>/<style> blocks are masked before scanning. Generic
     hedge words (synthetic, demo, sample) do NOT act as an allower on
     their own; they must co-occur with one of the rules above in the
     same sentence.
  5. Link / surface: key public links exist in the repo:
     /verify.html#trust-ledger anchor, receipt JSONs, receipt sidecars,
     standalone-verifier links resolve to files. No outbound network.

Usage:
    python3 scripts/release_gate.py            # gate the whole repo
    python3 scripts/release_gate.py --root .   # explicit root
    python3 scripts/release_gate.py --quiet    # only print failures

Exit codes:
    0  all checks passed
    1  one or more checks failed
    2  internal / IO error

Standard library only. Fast: <1s on the current repo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ----------------------------------------------------------------------
# Result accumulator
# ----------------------------------------------------------------------

@dataclass
class GateResult:
    passes: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def add_pass(self, msg: str) -> None:
        self.passes.append(msg)

    def add_fail(self, msg: str) -> None:
        self.failures.append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures


# ----------------------------------------------------------------------
# Public surface — files the gate inspects for claim language.
# Anything deployed to hardseal.ai is in scope. The repo root *.html
# files are the primary public surface; blog/, proof/ir/, and research/
# subdirectories also ship as public HTML and must be scanned. Anything
# not in this glob set is treated as out of scope.
# ----------------------------------------------------------------------

PUBLIC_HTML_GLOBS = (
    "*.html",
    "blog/*.html",
    "proof/ir/*.html",
    "research/**/*.html",
)

# Explicit per-relative-path skip list. The gate refuses to silently
# extend coverage; every skip must be named here with a reason.
PUBLIC_HTML_EXCLUDE: set[str] = {
    # 404 page does not carry product claims.
    "404.html",
}

# Public receipts and their sidecars. Order matters: index 0 is Receipt #1.
PUBLIC_RECEIPTS = (
    "sample-packet-receipt1.json",
    "cmmc-audit-log-receipt2.json",
    "poam-evidence-receipt3.json",
    "ssp-change-history-receipt4.json",
)


# ----------------------------------------------------------------------
# Check 1: proof artifacts
# ----------------------------------------------------------------------

def _read_sidecar_digest(sidecar_path: Path) -> str | None:
    """Sidecar format: '<sha256>  <filename>\\n'. Return the hex digest."""
    try:
        text = sidecar_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    # First whitespace-delimited token is the digest.
    return text.split()[0].lower()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_proof_artifacts(root: Path, result: GateResult) -> None:
    for name in PUBLIC_RECEIPTS:
        receipt = root / name
        sidecar = root / f"{name}.sha256"

        if not receipt.exists():
            result.add_fail(f"[proof] missing receipt: {receipt}")
            continue
        if not sidecar.exists():
            result.add_fail(
                f"[proof] missing sidecar: {sidecar} "
                f"(every public receipt must have a .sha256 sidecar)"
            )
            continue

        expected = _read_sidecar_digest(sidecar)
        if not expected:
            result.add_fail(f"[proof] empty or malformed sidecar: {sidecar}")
            continue

        observed = _sha256_file(receipt)
        if observed != expected:
            result.add_fail(
                f"[proof] sidecar hash mismatch for {receipt}: "
                f"expected {expected}, observed {observed}"
            )
            continue

        result.add_pass(f"[proof] {name}: sidecar matches recomputed SHA-256")

    # If the standalone verifier is present, exercise it on EVERY public
    # receipt — not just Receipt #1. The contract is strict:
    #   - subprocess returncode must be 0
    #   - the verifier's summary line must say `result: PASS`
    #   - no `FAIL` token may appear anywhere in the output (the
    #     verifier prints `  FAIL: ...` for failed sub-checks)
    # We try downloads/ first (linked from verify.html); fall back to
    # proof/ir/ if downloads/ is absent.
    verifier_candidates = (
        root / "downloads" / "verify_standalone.py",
        root / "proof" / "ir" / "verify_standalone.py",
    )
    verifier = next((p for p in verifier_candidates if p.exists()), None)

    if verifier is None:
        result.add_pass("[proof] standalone verifier not present (check skipped)")
        return

    for name in PUBLIC_RECEIPTS:
        receipt = root / name
        if not receipt.exists():
            # Already reported above; skip the verifier on missing input.
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(verifier), str(receipt)],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.add_fail(
                f"[proof] verifier invocation error on {name}: {exc}"
            )
            continue

        combined = (proc.stdout or "") + (proc.stderr or "")
        problems: list[str] = []
        if proc.returncode != 0:
            problems.append(f"returncode={proc.returncode} (expected 0)")
        if not re.search(r"^result:\s*PASS\s*$", combined, re.MULTILINE):
            problems.append("missing 'result: PASS' summary line")
        # The verifier emits sub-check failures as lines starting with
        # whitespace + 'FAIL:' (see verify_standalone.py:render). Catch
        # any such line — the summary 'result: PASS' alone is not enough
        # if any sub-check failed.
        if re.search(r"^\s*FAIL:", combined, re.MULTILINE):
            problems.append("output contains a sub-check 'FAIL:' line")

        if problems:
            tail = combined.strip().splitlines()[-12:]
            result.add_fail(
                f"[proof] standalone verifier did not cleanly PASS on {name}: "
                + "; ".join(problems)
                + ". Tail of output:\n    " + "\n    ".join(tail)
            )
        else:
            result.add_pass(f"[proof] standalone verifier clean PASS on {name}")


# ----------------------------------------------------------------------
# Check 2: Trust Ledger labeling
# ----------------------------------------------------------------------

# Accept "Receipts #1-#4 · Index", "Receipts #1–#4 Index", "Receipts #1 to
# #4 Ledger", etc. The dash class includes ASCII '-', en dash '–', em
# dash '—', and the word "to".
_LEDGER_LABEL_RE = re.compile(
    r"Receipts?\s*#?\s*1\s*(?:-|–|—|to)\s*#?\s*4\s*(?:[·•|–—-]\s*)?(?:Index|Ledger|index|ledger)",
    re.IGNORECASE,
)

# Mention of Receipt #5 INSIDE the trust-ledger block. The block is
# defined as the trust-ledger element (id="trust-ledger") and its inner
# HTML. The next packet receipt being numbered #5 in some FUTURE row
# is the operator's call elsewhere on the page; what we forbid is
# Receipt #5 appearing AS PART OF the ledger.
_LEDGER_HAS_5_RE = re.compile(
    r"Receipt\s*#?\s*5\b", re.IGNORECASE,
)


def _extract_trust_ledger_block(text: str) -> str | None:
    """Return the inner-HTML chunk that constitutes the trust-ledger block.

    Strategy: find the opening element with id="trust-ledger" (single or
    double quotes), then walk a depth counter over <div>/</div> to find
    its matching close. Falls back to a generous 8000-char window if the
    block uses tags other than <div>; the table inside the ledger is
    captured either way.
    """
    m = re.search(r'<(\w+)[^>]*\bid\s*=\s*["\']trust-ledger["\'][^>]*>',
                  text, re.IGNORECASE)
    if not m:
        return None
    tag = m.group(1).lower()
    # Walk depth from m.end() until the matching close.
    open_re = re.compile(rf"<{tag}\b[^>]*>", re.IGNORECASE)
    close_re = re.compile(rf"</{tag}\s*>", re.IGNORECASE)
    pos = m.end()
    depth = 1
    while depth > 0 and pos < len(text):
        next_open = open_re.search(text, pos)
        next_close = close_re.search(text, pos)
        if not next_close:
            return None  # unbalanced; bail
        if next_open and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
        else:
            depth -= 1
            pos = next_close.end()
            if depth == 0:
                return text[m.start():pos]
    return None


def check_trust_ledger(root: Path, result: GateResult) -> None:
    verify_html = root / "verify.html"
    if not verify_html.exists():
        result.add_fail("[ledger] verify.html missing — Trust Ledger lives there")
        return

    text = verify_html.read_text(encoding="utf-8", errors="replace")
    block = _extract_trust_ledger_block(text)
    if block is None:
        result.add_fail(
            f"[ledger] {verify_html}: could not locate <... id=\"trust-ledger\"> "
            f"block — the ledger element is missing or malformed"
        )
        return

    # Label must appear INSIDE the ledger block. A correct label elsewhere
    # on the page (header, footer) does not save a mislabeled block.
    if not _LEDGER_LABEL_RE.search(block):
        result.add_fail(
            f"[ledger] {verify_html}: trust-ledger block is not labeled as "
            f"'Receipts #1-#4 Index' (or equivalent index/ledger wording)"
        )
    else:
        result.add_pass("[ledger] trust-ledger block labeled as Receipts #1-#4 index")

    # Receipt #5 must not appear INSIDE the ledger block at all. The
    # next packet release shipping as Receipt #5 happens in a separate
    # part of the page (a packet section / quickstart), not inside the
    # ledger index itself.
    if _LEDGER_HAS_5_RE.search(block):
        result.add_fail(
            f"[ledger] {verify_html}: trust-ledger block mentions Receipt #5 — "
            f"the ledger is an index of Receipts #1-#4, not Receipt #5"
        )
    else:
        result.add_pass("[ledger] trust-ledger block does not mention Receipt #5")


# ----------------------------------------------------------------------
# Check 3: Receipt #2 mapping
# ----------------------------------------------------------------------

RECEIPT2_ALLOWED = {"AU.L2-3.3.1", "AU.L2-3.3.2", "AU.L2-3.3.8"}
RECEIPT2_FORBIDDEN = {
    "AU.L2-3.3.3", "AU.L2-3.3.4", "AU.L2-3.3.5",
    "AU.L2-3.3.6", "AU.L2-3.3.7",
}

# Words that, if they appear within a small window before a forbidden
# AU.L2-3.3.x token, mark the mention as a negation / future / prohibition
# note rather than a Receipt #2 claim.
_NEGATION_NEAR_RE = re.compile(
    r"\b(not|never|no|without|cannot|will not|won't|future|roadmap|"
    r"forthcoming|planned|exclud(?:ed|ing|es)|out of scope|outside scope|"
    r"prohibit(?:ed|ion|s)?|forbidden|banned|disallow(?:ed)?|"
    r"do(?:es)? not|don't)\b",
    re.IGNORECASE,
)


_RECEIPT2_ANCHOR_RE = re.compile(
    r"Receipt\s*#?\s*2\b|cmmc-audit-log-receipt2\.json|\breceipt2\b",
    re.IGNORECASE,
)

# Row-level container tags used to scope a Receipt #2 mapping claim. We
# pick the smallest enclosing element of one of these row-level tags —
# they correspond to "the whole Receipt #2 row" rather than a single
# inline cell or list item. <tr> covers the trust-ledger table; <div>
# with role-like classes (.quickstart) covers the per-receipt section.
_RECEIPT_BLOCK_TAGS = ("tr", "div", "section", "article")


def _enclosing_block(text: str, offset: int) -> tuple[int, int]:
    """Return (start, end) of the smallest enclosing row-level element
    containing `offset` — a <tr>, <div>, <section>, or <article>. We
    skip generic inline containers (<li>, <td>, <p>) because the Receipt
    #2 row in this repo's verify.html places the receipt anchor and its
    mapping line in sibling children of the same <div class="quickstart">.
    Falls back to an 800-char symmetric window if no row-level tag
    encloses the offset.
    """
    best: tuple[int, int] | None = None
    for tag in _RECEIPT_BLOCK_TAGS:
        open_re = re.compile(rf"<{tag}\b[^>]*>", re.IGNORECASE)
        close_re = re.compile(rf"</{tag}\s*>", re.IGNORECASE)
        opens = [m for m in open_re.finditer(text, 0, offset)]
        if not opens:
            continue
        for om in reversed(opens):
            depth = 1
            pos = om.end()
            matched_close: int | None = None
            while pos < len(text):
                no = open_re.search(text, pos)
                nc = close_re.search(text, pos)
                if not nc:
                    break
                if no and no.start() < nc.start():
                    depth += 1
                    pos = no.end()
                else:
                    depth -= 1
                    if depth == 0:
                        if nc.end() > offset:
                            matched_close = nc.end()
                        break
                    pos = nc.end()
            if matched_close is not None and om.start() <= offset < matched_close:
                span = matched_close - om.start()
                if best is None or span < (best[1] - best[0]):
                    best = (om.start(), matched_close)
                break
    if best is not None:
        return best
    return (max(0, offset - 400), min(len(text), offset + 400))


def check_receipt2_mapping(root: Path, result: GateResult) -> None:
    """Scan verify.html for Receipt #2 mapping claims.

    Strategy: every Receipt #2 anchor (the textual reference) defines a
    Receipt #2 block — the smallest enclosing div/section/article/tr/li/
    p/td element. AU.L2-3.3.x tokens INSIDE that block are Receipt #2
    mapping claims. Tokens outside any Receipt #2 block are not Receipt
    #2 claims and are not checked here.
    """
    verify_html = root / "verify.html"
    if not verify_html.exists():
        return  # already reported by ledger check

    text = verify_html.read_text(encoding="utf-8", errors="replace")

    # Identify every Receipt #2 mapping block.
    blocks: list[tuple[int, int]] = []
    for am in _RECEIPT2_ANCHOR_RE.finditer(text):
        b = _enclosing_block(text, am.start())
        if b not in blocks:
            blocks.append(b)

    if not blocks:
        result.add_fail(
            f"[receipt2] {verify_html}: no Receipt #2 block found "
            f"(expected at least one element mentioning 'Receipt #2')"
        )
        return

    found_allowed: set[str] = set()
    overbroad_hits: list[str] = []
    token_re = re.compile(r"AU\.L2-3\.3\.[1-8]")

    for b_start, b_end in blocks:
        block_text = text[b_start:b_end]
        # A passing back-reference to another receipt ("same verifier as
        # Receipt #1") does not disqualify this block — we trust the
        # row-level tag scoping. If a Receipt #2 block ALSO contains
        # another receipt's PRIMARY artifact filename (an actual link
        # to Receipt #3's JSON, which only the trust-ledger ROW for #3
        # would carry), THAT row's <tr> would be a separate block, not
        # this one.
        for m in token_re.finditer(block_text):
            token = m.group(0)
            abs_start = b_start + m.start()
            if token in RECEIPT2_ALLOWED:
                found_allowed.add(token)
                continue
            if token in RECEIPT2_FORBIDDEN:
                local_window = text[max(0, abs_start - 120): abs_start + len(token) + 60]
                if _NEGATION_NEAR_RE.search(local_window):
                    continue
                line_no = text.count("\n", 0, abs_start) + 1
                overbroad_hits.append(f"line {line_no}: {token}")

    if overbroad_hits:
        result.add_fail(
            f"[receipt2] {verify_html}: Receipt #2 mapping broadened beyond "
            f"{sorted(RECEIPT2_ALLOWED)}: "
            + "; ".join(overbroad_hits)
        )
    else:
        result.add_pass(
            f"[receipt2] mapping stays within "
            f"{sorted(RECEIPT2_ALLOWED)}"
        )

    missing = RECEIPT2_ALLOWED - found_allowed
    if missing:
        result.add_fail(
            f"[receipt2] {verify_html}: Receipt #2 row is missing expected "
            f"mapping(s): {sorted(missing)}"
        )
    else:
        result.add_pass("[receipt2] all three allowed mappings present")


# ----------------------------------------------------------------------
# Check 4: overclaim firewall
# ----------------------------------------------------------------------

# Phrases that, when used as unqualified affirmative public claims, would
# overclaim Hardseal's posture.
#
# `whole_word` controls whether the match requires word boundaries on
# both sides. Short ambiguous tokens (signed, certified, compliant,
# enclave) MUST use whole_word=True or they match inside designed,
# assigned, compliant-with, etc. Longer multi-word phrases match
# substring-style (their length makes false matches unlikely).
#
# Overlapping phrases are de-duped by offset below so each location is
# reported once with its longest match.
OVERCLAIM_PHRASES: tuple[tuple[str, bool], ...] = (
    ("signed", True),
    ("signature", True),
    ("Ed25519", True),
    ("certified", True),
    ("compliant", True),
    ("compliance proof", False),
    ("customer evidence", False),
    ("production deployment", False),
    ("enclave", True),
    ("private key", False),
    ("C3PAO approved", False),
    ("audit ready", False),
    ("tamper-evident", False),
    ("tamper detection", False),
    ("unaltered", True),
    ("has not been altered", False),
    ("changed after it was created", False),
    ("detects any tampering", False),
    ("tampered with after the fact", False),
)

# Negation / prohibition / roadmap qualifier. Applied ONLY within the
# same sentence as the hit. Strict word-list — "demo" or "synthetic"
# alone are NOT in here because they describe an artifact's status, not
# a qualifier attached to the claim.
_NEGATION_RE = re.compile(
    r"\b(not|no|never|without|cannot|can't|won't|will\s+not|"
    r"do(?:es)?\s+not|don't|isn't|aren't|wasn't|weren't|"
    r"prohibit(?:ed|ion|s)?|forbidden|banned|disallow(?:ed)?|"
    r"withheld|exclud(?:ed|ing|es)|"
    r"out\s+of\s+scope|outside\s+scope|nothing\s+(?:in|on)\s+this|"
    r"not\s+yet|yet\s+to|todo)\b",
    re.IGNORECASE,
)

_ROADMAP_RE = re.compile(
    r"\b(future|roadmap|on\s+the\s+roadmap|planned|forthcoming|deferred|"
    r"intended|if\s+and\s+when|coming\s+soon|pre-release|pre-assessment)\b",
    re.IGNORECASE,
)

# Contract context — ONLY relaxes the `signed`/`signature` phrases, and
# ONLY when the sentence is clearly about a signed legal document.
# Requires a legal-document noun in the same sentence.
_CONTRACT_NOUN_RE = re.compile(
    r"\b(agreement|MSA|Master\s+Services\s+Agreement|SOW|Statement\s+of\s+Work|"
    r"Subscription\s+Order|written\s+amendment|amendment|engagement|"
    r"Customer\s+engagements?|contract|DPA|"
    r"Data\s+Processing\s+Addendum|order\s+form|order|"
    r"this\s+Agreement|the\s+Agreement)\b",
    re.IGNORECASE,
)

# Customer-owned environment — ONLY relaxes the `enclave` phrase, and
# ONLY when the possessive form ("Customer's enclave", "client's enclave"
# or "the customer's <something> enclave") makes it explicit that the
# enclave belongs to the customer, NOT Hardseal. Generic "customer
# enclave" (without possessive) is intentionally NOT allowed — it is
# ambiguous and "Hardseal runs in a customer enclave" should fail.
_CUSTOMER_POSSESSIVE_ENCLAVE_RE = re.compile(
    r"\b(?:Customer'?s|Client'?s|your)\s+(?:[\w\-]+\s+){0,3}enclave\b|"
    r"\b(?:Customer-designated|Customer-controlled)\s+(?:[\w\-]+\s+){0,3}enclave\b|"
    r"\benclave\s+(?:under|that\s+Customer|controlled\s+by\s+Customer)\b|"
    r"\bone\s+(?:client|customer)\s+enclave\b|"
    r"\baccess\s+to\s+(?:one\s+)?client\s+enclave\b|"
    r"\bper-enclave\s+licensing\b|"
    r"\bone\s+defined\s+client\s+environment\s+\(1\s+enclave\)|"
    r"\bsingle\s+real\s+\(or\s+representative\)\s+CMMC\s+Level\s+\d\s+enclave\b|"
    r"\bconfigure\s+for\s+enclave\b|"
    r"\bdeploy\s+Hardseal,\s+configure\s+for\s+enclave\b",
    re.IGNORECASE,
)

# HMAC-SHA256 factual filename / artifact name — relaxes only
# `signed`/`signature`, and only when HMAC-SHA256 is adjacent (same
# sentence, within 60 chars).
_HMAC_NEAR_RE = re.compile(r"HMAC[-\s]?SHA[-\s]?256", re.IGNORECASE)

# "detection signature" / "detection signatures" / "signature-only" —
# domain terminology meaning a detection rule, not a cryptographic
# signature. Relaxes ONLY the `signature` phrase.
_DETECTION_SIGNATURE_RE = re.compile(
    r"\b(?:detection|seven\s+detection|five\s+signature(?:-only)?|"
    r"statistical|regex|stylometric|fingerprint)\s+signatures?\b|"
    r"\bsignature[-\s]only\b|"
    r"\bsignatures?\s+(?:for|of|under\s+MIT|shipping)\b",
    re.IGNORECASE,
)

## NOTE: previous versions accepted a generic "hedge" qualifier
## (synthetic / demo / sample / etc.) within a 250-char window. That was
## too permissive: a single hedge word in an unrelated nearby sentence
## allowed a real overclaim to pass. The current design REMOVES that
## allowance and replaces it with sentence-scoped, concept-specific
## allowed contexts. The hedge words still appear in the public surface
## (and are good) but they no longer act as an overclaim allower.


@dataclass
class AllowlistEntry:
    """An explicit overclaim-firewall exception.

    Keep this list small and justified. Each entry pins a phrase to a
    specific file (and optional pattern) so the exception cannot silently
    grow to cover new affirmative claims.
    """
    file: str           # path relative to repo root
    phrase: str         # exact phrase (lowercase) to allow
    pattern: str        # short substring that must appear on the line
    justification: str  # why this is OK


# Explicit allowlist. Start empty; populate only after the gate is wired
# and a real hit needs justification. The CONTEXT_RULES below cover the
# documented categories (negations, prohibition text, banned-phrase
# arrays, roadmap qualifiers, factual HMAC names) generically.
OVERCLAIM_ALLOWLIST: tuple[AllowlistEntry, ...] = ()


def _line_at(text: str, offset: int) -> tuple[int, str]:
    """Return (line_number_1based, full_line_text) for a given offset."""
    line_no = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = len(text)
    return line_no, text[line_start:line_end]


# Sentence-boundary regex. A sentence ends at ., !, ?, or ;, optionally
# followed by closing quote/paren/bracket and required whitespace; OR at
# an HTML block boundary (<br>, </p>, </li>, </td>, </h\d>, list items).
# We deliberately split on `:` ONLY when it's followed by a paragraph
# break ("Note:\n"), to avoid eating ":" in "AU.L2-3.3.1: …".
_SENTENCE_SPLIT_RE = re.compile(
    r"(?:"
    # Punctuation followed by closing wrappers, then whitespace.
    r"[.!?;](?:['\"\)\]]*)\s+|"
    # HTML block-end tags.
    r"</(?:p|li|td|th|h[1-6]|div|section|article)\s*>|"
    # HTML inline breaks.
    r"<br\s*/?>|"
    # Double newline (paragraph break).
    r"\n\s*\n"
    r")",
    re.IGNORECASE,
)


def _enclosing_sentence(text: str, hit_start: int, hit_end: int) -> str:
    """Return the smallest sentence-like span containing the hit.

    Sentence boundary on the LEFT: the nearest preceding sentence
    terminator or HTML block-end / paragraph break (whichever is closer).
    Sentence boundary on the RIGHT: the nearest following such terminator
    AT OR AFTER the hit-end. The returned span includes both boundaries'
    inside text but NOT the terminators themselves.
    """
    # Left boundary: scan backward from hit_start.
    left_bound = 0
    for m in _SENTENCE_SPLIT_RE.finditer(text, 0, hit_start):
        # Use the *end* of the splitter as the start of the next sentence.
        left_bound = m.end()
    # Right boundary: scan forward from hit_end.
    right_bound = len(text)
    m = _SENTENCE_SPLIT_RE.search(text, hit_end)
    if m:
        right_bound = m.start()
    return text[left_bound:right_bound]


def _is_allowed_context(
    text: str, hit_start: int, hit_end: int, phrase: str, file_rel: str,
) -> tuple[bool, str]:
    """Decide whether this overclaim hit is in an allowed context.

    Allowed contexts are SENTENCE-SCOPED and CONCEPT-SPECIFIC:
      * negation / prohibition in the same sentence: allows any phrase
      * roadmap qualifier in the same sentence: allows any phrase
      * contract noun in the same sentence: allows `signed`/`signature`
      * possessive customer-owned-enclave phrasing in the same sentence:
        allows `enclave`
      * HMAC-SHA256 in the same sentence: allows `signed`/`signature`
      * detection-signature domain phrasing in the same sentence:
        allows `signature`
      * explicit allowlist entry (file + phrase + line-substring): any

    Generic hedge words (synthetic, demo, sample) on their own do NOT
    allow a hit — they describe the artifact's status, not a qualifier
    attached to the claim. If a real claim needs them as a qualifier,
    they must co-occur with one of the rules above in the same sentence.
    """
    # 1. Explicit allowlist match.
    line_no, line = _line_at(text, hit_start)
    for entry in OVERCLAIM_ALLOWLIST:
        if entry.file != file_rel:
            continue
        if entry.phrase != phrase.lower():
            continue
        if entry.pattern and entry.pattern not in line:
            continue
        return True, f"allowlist: {entry.justification}"

    sentence = _enclosing_sentence(text, hit_start, hit_end)
    p = phrase.lower()

    # 2. Negation / prohibition in the same sentence — applies to all.
    if _NEGATION_RE.search(sentence):
        return True, "negation / prohibition in same sentence"

    # 3. Roadmap qualifier in the same sentence — applies to all.
    if _ROADMAP_RE.search(sentence):
        return True, "roadmap qualifier in same sentence"

    # 4. HMAC-SHA256 factual file-name context — relaxes only signed/signature.
    if p in {"signed", "signature"} and _HMAC_NEAR_RE.search(sentence):
        return True, "HMAC-SHA256 factual reference in same sentence"

    # 5. Contract context — relaxes only signed/signature, and requires
    #    a contract noun in the same sentence.
    if p in {"signed", "signature"} and _CONTRACT_NOUN_RE.search(sentence):
        return True, "contract context (signed agreement) in same sentence"

    # 6. Customer-owned enclave — relaxes only enclave, requires
    #    possessive / customer-explicit phrasing in the same sentence.
    if p == "enclave" and _CUSTOMER_POSSESSIVE_ENCLAVE_RE.search(sentence):
        return True, "customer/client-owned enclave (possessive) in same sentence"

    # 7. Detection-signature domain use — relaxes only `signature`.
    if p == "signature" and _DETECTION_SIGNATURE_RE.search(sentence):
        return True, "detection-signature domain term in same sentence"

    return False, ""


def _iter_public_html(root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in PUBLIC_HTML_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in PUBLIC_HTML_EXCLUDE:
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def _build_overclaim_pattern() -> re.Pattern[str]:
    # Sort by length descending so longer phrases consume their span
    # before shorter substrings match at the same offset.
    sorted_phrases = sorted(OVERCLAIM_PHRASES, key=lambda p: len(p[0]), reverse=True)
    parts = []
    for phrase, whole_word in sorted_phrases:
        esc = re.escape(phrase)
        if whole_word:
            esc = r"\b" + esc + r"\b"
        parts.append(esc)
    return re.compile("|".join(parts), re.IGNORECASE)


# Mask <script>...</script> and <style>...</style> blocks. JS source and
# CSS are not user-visible claim text; the verifier's banned-phrase
# arrays live inside <script>. We preserve byte offsets by replacing
# matched characters with spaces, so line numbers from re.finditer on
# the masked text still align with the original.
_SCRIPT_STYLE_RE = re.compile(
    r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>",
    re.IGNORECASE | re.DOTALL,
)


def _mask_script_style(text: str) -> str:
    def _blank(m: re.Match[str]) -> str:
        s = m.group(0)
        # Keep newlines so line counts stay aligned.
        return "".join("\n" if c == "\n" else " " for c in s)
    return _SCRIPT_STYLE_RE.sub(_blank, text)


def check_overclaim_firewall(root: Path, result: GateResult) -> None:
    pattern = _build_overclaim_pattern()

    total_files = 0
    total_hits = 0
    unsupported: list[str] = []

    for html in _iter_public_html(root):
        total_files += 1
        raw = html.read_text(encoding="utf-8", errors="replace")
        text = _mask_script_style(raw)
        file_rel = html.relative_to(root).as_posix()
        seen_offsets: set[int] = set()

        for m in pattern.finditer(text):
            if m.start() in seen_offsets:
                continue
            seen_offsets.add(m.start())
            total_hits += 1
            phrase = m.group(0)
            allowed, _reason = _is_allowed_context(
                text, m.start(), m.end(), phrase, file_rel,
            )
            if allowed:
                continue
            line_no, line = _line_at(text, m.start())
            snippet = line.strip()
            if len(snippet) > 160:
                snippet = snippet[:157] + "..."
            unsupported.append(
                f"{file_rel}:{line_no}: unsupported affirmative claim "
                f"'{phrase}': {snippet}"
            )

    if unsupported:
        for u in unsupported:
            result.add_fail(f"[overclaim] {u}")
    else:
        result.add_pass(
            f"[overclaim] no unsupported affirmative claims across "
            f"{total_files} public HTML file(s) ({total_hits} hits, all in "
            f"allowed contexts)"
        )


# ----------------------------------------------------------------------
# Check 5: link / surface
# ----------------------------------------------------------------------

def check_links(root: Path, result: GateResult) -> None:
    verify_html = root / "verify.html"

    # Anchor #trust-ledger exists in verify.html.
    if verify_html.exists():
        text = verify_html.read_text(encoding="utf-8", errors="replace")
        if 'id="trust-ledger"' in text or "id='trust-ledger'" in text:
            result.add_pass("[links] /verify.html#trust-ledger anchor present")
        else:
            result.add_fail(
                f"[links] {verify_html}: #trust-ledger anchor missing — "
                f"outbound links to /verify.html#trust-ledger would 404 to top"
            )
    else:
        result.add_fail("[links] verify.html missing — public verify surface is gone")
        text = ""

    # Every public receipt and sidecar exists at the expected path. The
    # sidecar must additionally name its receipt file in its body (the
    # second whitespace-delimited token is `<filename>` per sha256sum
    # convention) — this catches "sidecar for the wrong file".
    artifacts_ok = True
    for name in PUBLIC_RECEIPTS:
        receipt = root / name
        sidecar = root / f"{name}.sha256"
        if not receipt.exists():
            result.add_fail(f"[links] expected public artifact missing: {receipt}")
            artifacts_ok = False
        if not sidecar.exists():
            result.add_fail(f"[links] expected public artifact missing: {sidecar}")
            artifacts_ok = False
            continue
        # Validate sidecar filename token.
        try:
            sidecar_text = sidecar.read_text(encoding="utf-8").strip()
        except OSError as exc:
            result.add_fail(f"[links] cannot read sidecar {sidecar}: {exc}")
            artifacts_ok = False
            continue
        tokens = sidecar_text.split()
        if len(tokens) >= 2 and tokens[1] != name:
            result.add_fail(
                f"[links] sidecar {sidecar} names {tokens[1]!r} but should "
                f"name {name!r} — sidecar is pointing at the wrong file"
            )
            artifacts_ok = False
    if artifacts_ok:
        result.add_pass(
            f"[links] all {len(PUBLIC_RECEIPTS)} receipts + sidecars present, "
            f"sidecars name the correct receipt file"
        )

    # If verify.html links the standalone verifier, the verifier must exist.
    if verify_html.exists():
        bad = 0
        total = 0
        for m in re.finditer(
            r'href=["\']([^"\']*verify_standalone\.py[^"\']*)["\']', text,
        ):
            total += 1
            href = m.group(1)
            local = href.lstrip("/").split("?", 1)[0].split("#", 1)[0]
            if not local:
                continue
            if not (root / local).exists():
                line_no, _ = _line_at(text, m.start())
                result.add_fail(
                    f"[links] verify.html:{line_no}: links {href} but "
                    f"{root / local} does not exist in repo"
                )
                bad += 1
        if total > 0 and bad == 0:
            result.add_pass(
                f"[links] all {total} standalone-verifier link(s) "
                f"resolve to files in repo"
            )


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------

def run_all(root: Path) -> GateResult:
    result = GateResult()
    check_proof_artifacts(root, result)
    check_trust_ledger(root, result)
    check_receipt2_mapping(root, result)
    check_overclaim_firewall(root, result)
    check_links(root, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hardseal release gate — fail on drift before public deploy.",
    )
    parser.add_argument(
        "--root", default=".",
        help="Repository root to gate (default: current directory).",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Only print failures and the final result.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"release_gate: --root {root} is not a directory", file=sys.stderr)
        return 2

    try:
        result = run_all(root)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"release_gate: internal error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        for p in result.passes:
            print(f"  PASS: {p}")
    for f in result.failures:
        print(f"  FAIL: {f}")

    print()
    if result.ok:
        print(f"release gate: PASS ({len(result.passes)} checks)")
        return 0
    print(
        f"release gate: FAIL ({len(result.failures)} failure(s), "
        f"{len(result.passes)} pass(es))"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
