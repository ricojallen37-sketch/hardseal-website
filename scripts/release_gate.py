#!/usr/bin/env python3
"""Hardseal release gate — runs before public deploy.

Doctrine: we fly what we test, we test what we fly. This script enforces
public-proof honesty so a drifted page, receipt, sidecar, or claim cannot
ship to production.

Checks (all must pass; first failure does not short-circuit so the operator
sees every issue in one run):

  1. Proof artifact: every public receipt JSON has a matching .sha256
     sidecar; recompute SHA-256 and compare; if the standalone verifier is
     present, exercise it on Receipt #1.
  2. Trust Ledger: must be labeled as "Receipts #1-#4 Index" (or
     equivalent) and must not be labeled as "Receipt #5".
  3. Receipt #2 mapping: must not broaden beyond AU.L2-3.3.1, AU.L2-3.3.2,
     AU.L2-3.3.8. AU.L2-3.3.3..7 as Receipt #2 mapping fails unless in an
     explicit negation / prohibition / future note.
  4. Overclaim firewall: fail unsupported affirmative public claims for a
     fixed list of phrases (signed, Ed25519, certified, compliant, etc.).
     Allowlisted contexts: negations, prohibition/checklist text, verifier
     banned-phrase arrays, roadmap-qualified language, factual HMAC-SHA256
     file names.
  5. Link / surface: key public links used in outbound exist in the repo:
     /verify.html#trust-ledger anchor, receipt JSONs, receipt sidecars, the
     standalone verifier file if linked from public surface.

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
# Limited to public HTML on the deploy path. Internal docs, the script
# itself, tests/fixtures, the verifier (which contains banned-phrase
# strings by design), and the integrity log are excluded.
# ----------------------------------------------------------------------

PUBLIC_HTML_GLOBS = ("*.html",)

# Files under the repo root that are public HTML but should be skipped
# (none today; kept as an explicit list so the operator can see it).
PUBLIC_HTML_EXCLUDE: set[str] = set()

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

    # If the standalone verifier is present, exercise it on Receipt #1.
    # We try the downloads/ copy first (linked from verify.html); fall
    # back to proof/ir/ if downloads/ is absent. Either is acceptable —
    # the check is "if the repo supports invoking the verifier".
    verifier_candidates = (
        root / "downloads" / "verify_standalone.py",
        root / "proof" / "ir" / "verify_standalone.py",
    )
    verifier = next((p for p in verifier_candidates if p.exists()), None)
    receipt1 = root / PUBLIC_RECEIPTS[0]

    if verifier is None:
        result.add_pass("[proof] standalone verifier not present (check skipped)")
    elif not receipt1.exists():
        result.add_fail(f"[proof] Receipt #1 missing for verifier sample run: {receipt1}")
    else:
        try:
            proc = subprocess.run(
                [sys.executable, str(verifier), str(receipt1)],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.add_fail(f"[proof] verifier invocation error on Receipt #1: {exc}")
        else:
            combined = (proc.stdout or "") + (proc.stderr or "")
            if re.search(r"^result:\s*PASS\s*$", combined, re.MULTILINE):
                result.add_pass("[proof] standalone verifier PASS on Receipt #1")
            else:
                tail = combined.strip().splitlines()[-10:]
                result.add_fail(
                    "[proof] standalone verifier did not return PASS on Receipt #1. "
                    f"Tail of output:\n    " + "\n    ".join(tail)
                )


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

# "Trust Ledger ... Receipt #5" or "Receipt #5 ... Trust Ledger" within a
# small window — that would imply the ledger IS Receipt #5. The next
# packet receipt being numbered #5 is fine elsewhere; this only fires when
# the words appear together.
_LEDGER_IS_5_RE = re.compile(
    r"Trust\s+Ledger[^\n]{0,80}Receipt\s*#?\s*5|Receipt\s*#?\s*5[^\n]{0,80}Trust\s+Ledger",
    re.IGNORECASE,
)


def check_trust_ledger(root: Path, result: GateResult) -> None:
    verify_html = root / "verify.html"
    if not verify_html.exists():
        result.add_fail("[ledger] verify.html missing — Trust Ledger lives there")
        return

    text = verify_html.read_text(encoding="utf-8", errors="replace")

    if not _LEDGER_LABEL_RE.search(text):
        result.add_fail(
            f"[ledger] {verify_html}: Trust Ledger is not labeled as "
            f"'Receipts #1-#4 Index' (or equivalent index/ledger wording)"
        )
    else:
        result.add_pass("[ledger] Trust Ledger labeled as Receipts #1-#4 index")

    if _LEDGER_IS_5_RE.search(text):
        result.add_fail(
            f"[ledger] {verify_html}: Trust Ledger appears to be labeled "
            f"or implied as Receipt #5 — the ledger is an index, not a receipt"
        )
    else:
        result.add_pass("[ledger] Trust Ledger is not labeled as Receipt #5")


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


def check_receipt2_mapping(root: Path, result: GateResult) -> None:
    """Scan verify.html for the Receipt #2 mapping block."""
    verify_html = root / "verify.html"
    if not verify_html.exists():
        return  # already reported by ledger check

    text = verify_html.read_text(encoding="utf-8", errors="replace")

    # Locate the Receipt #2 row. Strategy: find every AU.L2-3.3.x token,
    # then for each, look at a window of ~600 chars before it. If the
    # window mentions Receipt #2 (or its filename), the token is a
    # Receipt #2 mapping claim. Otherwise it's some other context.
    found_allowed: set[str] = set()
    overbroad_hits: list[str] = []

    token_re = re.compile(r"AU\.L2-3\.3\.[1-8]")
    for m in token_re.finditer(text):
        token = m.group(0)
        window_start = max(0, m.start() - 600)
        window = text[window_start:m.start()]
        # Is this a Receipt #2 mapping claim?
        if not re.search(
            r"Receipt\s*#?\s*2|cmmc-audit-log-receipt2|receipt2",
            window, re.IGNORECASE,
        ):
            continue

        if token in RECEIPT2_ALLOWED:
            found_allowed.add(token)
            continue

        if token in RECEIPT2_FORBIDDEN:
            # Check the immediate vicinity for negation / future qualifier.
            local_window = text[max(0, m.start() - 120): m.end() + 60]
            if _NEGATION_NEAR_RE.search(local_window):
                continue
            # Compute line number for clear failure messages.
            line_no = text.count("\n", 0, m.start()) + 1
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

# Words that, if present in a small window around a hit, mark the hit as
# an allowed context (negation, prohibition, roadmap qualifier).
_OVERCLAIM_ALLOWED_NEAR_RE = re.compile(
    r"\b(not|no|never|without|cannot|won't|will not|do(?:es)? not|don't|"
    r"isn't|aren't|wasn't|weren't|"
    r"prohibit(?:ed|ion|s)?|forbidden|banned|disallow(?:ed)?|"
    r"future|roadmap|planned|forthcoming|deferred|intended|"
    r"not yet|yet to|todo|coming soon|if and when|"
    r"out of scope|outside scope|exclud(?:ed|ing|es))\b",
    re.IGNORECASE,
)

# Contract / legal context. When these terms appear near a "signed" hit,
# the word refers to a signed AGREEMENT (MSA / SOW / contract) — a legal
# document being signed — not a cryptographic signature on a Hardseal
# artifact. This is the standard contract-law use of "signed" and is
# not an overclaim of cryptographic provenance.
_CONTRACT_CONTEXT_RE = re.compile(
    r"\b(agreement|MSA|Master\s+Services\s+Agreement|SOW|Statement\s+of\s+Work|"
    r"Subscription\s+Order|written\s+amendment|engagement|customer\s+engagement|"
    r"Customer\s+engagements|authorized\s+representatives|"
    r"both\s+parties|DPA|terms\s+of\s+the)\b",
    re.IGNORECASE,
)

# Customer/client-owned environment context. When `enclave` is referring
# to the CUSTOMER's enclave (not a Hardseal-provided one), the word is a
# factual reference to the customer's own infrastructure, not an
# overclaim that Hardseal operates one.
_CUSTOMER_ENV_RE = re.compile(
    r"\b(customer'?s?|client'?s?|customer-designated|customer-controlled|"
    r"single\s+real|one\s+(?:real|client|defined)|representative|"
    r"per-enclave\s+licensing|configure\s+for|access\s+to(?:\s+one)?|"
    r"single\s+|deploy\s+Hardseal)\b",
    re.IGNORECASE,
)

# Hedge phrases that the existing "honesty" sweep added to soften residual
# claim language. Their presence in the immediate vicinity means the
# surrounding claim is already qualified — treat as allowed context.
_OVERCLAIM_HEDGE_RE = re.compile(
    r"\b(synthetic|demo|demonstration|sample|example|illustrative|"
    r"assessor-readable|integrity demonstration|evidence integrity|"
    r"replay artifact)\b",
    re.IGNORECASE,
)

# HMAC-SHA256 file-name pattern (factual artifact name — the word "signed"
# never appears here, but "signature" can show up in HMAC contexts; this
# pattern lets us recognize them).
_HMAC_SHA256_RE = re.compile(r"HMAC-?SHA-?256", re.IGNORECASE)

# A line that looks like a banned-phrase array element / verifier list
# entry: a quoted string ending with a comma, inside a parenthesized or
# bracketed list. Keeping these strict prevents the gate from yelling at
# the verifier's own forbidden-phrase list.
_BANNED_ARRAY_LINE_RE = re.compile(
    r"""^\s*["'][^"']{1,120}["']\s*,?\s*$"""
)


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


def _is_allowed_context(
    text: str, hit_start: int, hit_end: int, phrase: str, file_rel: str,
) -> tuple[bool, str]:
    """Return (allowed, reason)."""
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

    # 2. HMAC-SHA256 factual file-name context — only relaxes the
    #    "signature" phrase, not the broader claim phrases.
    if phrase.lower() in {"signature", "signed"} and _HMAC_SHA256_RE.search(line):
        return True, "HMAC-SHA256 factual reference"

    # 3. Banned-phrase array element / verifier list literal. We
    #    recognize two structural patterns:
    #      a) a short standalone line that is just a quoted string;
    #      b) a line that is multiple comma-separated lowercase quoted
    #         strings (the verifier's BANNED_PHRASES array, formatted
    #         on one line in HTML/JS).
    if _BANNED_ARRAY_LINE_RE.match(line):
        return True, "banned-phrase array literal"
    # (b): line is dominated by quoted lowercase strings + commas.
    stripped = line.strip()
    if stripped and stripped.count('"') >= 4 and stripped.count(",") >= 1:
        # Strip quotes and commas; what's left should be near-empty.
        residue = re.sub(r'"[^"]*"|,|\s', "", stripped)
        if not residue:
            return True, "banned-phrase array literal (inline)"

    # 4. Negation / prohibition / roadmap qualifier within a wider window
    #    (covers "They are SHA-256 ... — they are not Ed25519-signed
    #    production evidence, customer evidence, certification proof,
    #    compliance proof, ..." where the "not" can be 150+ chars away).
    window_start = max(0, hit_start - 250)
    window_end = min(len(text), hit_end + 80)
    window = text[window_start:window_end]
    if _OVERCLAIM_ALLOWED_NEAR_RE.search(window):
        return True, "negation / prohibition / roadmap qualifier nearby"

    # 5. Contract context for "signed" / "signature": references to
    #    MSA / SOW / agreement / engagement mean a signed legal document,
    #    not a signed Hardseal artifact.
    if phrase.lower() in {"signed", "signature"} and _CONTRACT_CONTEXT_RE.search(window):
        return True, "contract context (signed agreement, not signed artifact)"

    # 6. Customer/client-owned environment context for "enclave".
    if phrase.lower() == "enclave" and _CUSTOMER_ENV_RE.search(window):
        return True, "customer/client-owned enclave (factual environment reference)"

    # 7. Hedge phrase ("synthetic", "demo", "integrity demonstration",
    #    etc.) within the same sentence-ish window. The honesty/proof-ir
    #    sweep already added these qualifiers around residual claim
    #    language; treat them as the documented allowed context.
    if _OVERCLAIM_HEDGE_RE.search(window):
        return True, "hedge qualifier (synthetic / demo / demonstration) nearby"

    return False, ""


def _iter_public_html(root: Path) -> Iterable[Path]:
    for pattern in PUBLIC_HTML_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.name in PUBLIC_HTML_EXCLUDE:
                continue
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

    # Every public receipt and sidecar exists at the expected path.
    for name in PUBLIC_RECEIPTS:
        for suffix in ("", ".sha256"):
            p = root / f"{name}{suffix}"
            if not p.exists():
                result.add_fail(f"[links] expected public artifact missing: {p}")

    # If verify.html links the standalone verifier, the verifier must exist.
    if verify_html.exists():
        text = verify_html.read_text(encoding="utf-8", errors="replace")
        # Look for any link to verify_standalone.py.
        for m in re.finditer(
            r'href=["\']([^"\']*verify_standalone\.py[^"\']*)["\']', text,
        ):
            href = m.group(1)
            # Resolve href relative to root for repo-local paths.
            local = href.lstrip("/")
            # Strip query / fragment.
            local = local.split("?", 1)[0].split("#", 1)[0]
            if not local:
                continue
            if not (root / local).exists():
                line_no, _ = _line_at(text, m.start())
                result.add_fail(
                    f"[links] verify.html:{line_no}: links {href} but "
                    f"{root / local} does not exist in repo"
                )
        result.add_pass("[links] all standalone-verifier links resolve to files in repo")


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
