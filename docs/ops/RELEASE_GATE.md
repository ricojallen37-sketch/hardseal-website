# Release Gate

Required release-gate check for public-proof honesty. If a public page, verifier, receipt, sidecar, or Trust Ledger claim drifts, the gate fails and the change must not ship.

**Script:** `scripts/release_gate.py` — standard library only, <1s on the current repo.
**Tests:** `scripts/test_release_gate.py` — negative-fixture suite proving the gate catches each documented failure mode.
**CI:** `.github/workflows/release-gate.yml` — runs on every push to `main` and every PR targeting `main`.

## Honest framing on deploy-blocking

This workflow alone does NOT block deployment. hardseal.ai is served via GitHub Pages legacy `build_type` from `main`; the Pages auto-build runs in parallel with this workflow on every push to `main` and cannot be pre-empted from a separate workflow.

**To make the gate a real deploy block, branch protection must be configured on `main`.** Until that happens, the gate is an after-the-fact red mark on offending commits and a required-status-check on PRs, not a deploy block on direct pushes.

The one-time configuration command (requires repo-admin auth):

```bash
gh api -X PUT repos/<owner>/hardseal-website/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks.strict=true \
  -F required_status_checks.contexts[]='release-gate / gate' \
  -f enforce_admins=true \
  -f required_pull_request_reviews.required_approving_review_count=1 \
  -f restrictions=
```

After branch protection is enabled, direct pushes to `main` are rejected and PR merges require this gate to pass; only commits that passed the gate end up on `main` and therefore trigger Pages rebuilds.

Verify with:

```bash
gh api repos/<owner>/hardseal-website/branches/main/protection
```

If this returns `Branch not protected`, the gate is documentation, not enforcement.

## Doctrine

- We fly what we test.
- We test what we fly.
- Receipts over summaries.
- No unsupported claims.

## Usage

```bash
# Gate the current working tree (default --root is the cwd).
python3 scripts/release_gate.py

# Explicit root.
python3 scripts/release_gate.py --root /path/to/checkout

# Only print failures.
python3 scripts/release_gate.py --quiet

# Run the gate's own negative-fixture tests.
python3 scripts/test_release_gate.py
```

Exit codes:

- `0` — all checks passed.
- `1` — one or more checks failed.
- `2` — internal / IO error.

## Checks

### 1. Proof artifacts

For every receipt JSON in `PUBLIC_RECEIPTS` (the four public demo packets):

- The matching `.sha256` sidecar must exist.
- Recomputed SHA-256 of the receipt must equal the digest in the sidecar.
- The sidecar's second whitespace-delimited token (the `sha256sum`-style filename) must equal the receipt's basename — a sidecar pointing at the wrong file is caught here.
- If `downloads/verify_standalone.py` (or `proof/ir/verify_standalone.py`) is present, the verifier is invoked on EVERY receipt (#1 through #4) and must:
  - exit with returncode `0`;
  - print `result: PASS` on its summary line;
  - emit NO sub-check `FAIL:` line anywhere in its output.

The gate never mutates packet JSON.

### 2. Trust Ledger labeling

The check is scoped to the `<... id="trust-ledger">` element and its inner HTML:

- The trust-ledger block must contain a label matching `Receipts #1-#4 · Index` (or equivalent — ASCII `-`, en/em dash, or `to` are accepted; `Index` or `Ledger` are accepted). A correct label in the page footer or elsewhere does NOT satisfy this check.
- The trust-ledger block must NOT contain `Receipt #5` anywhere. A future packet receipt numbered #5 is fine — but it appears in a separate per-receipt section, not inside the ledger index.
- If the `<... id="trust-ledger">` element is missing or unbalanced, the check fails explicitly.

### 3. Receipt #2 mapping

Receipt #2 maps to:

- `AU.L2-3.3.1`
- `AU.L2-3.3.2`
- `AU.L2-3.3.8`

Any appearance of `AU.L2-3.3.3` through `AU.L2-3.3.7` as a Receipt #2 mapping claim fails the gate.

The gate identifies a Receipt #2 block by walking outward from every Receipt #2 anchor (`Receipt #2`, `cmmc-audit-log-receipt2.json`, `receipt2`) to the nearest enclosing row-level tag — `<tr>`, `<div>`, `<section>`, or `<article>` — then scans `AU.L2-3.3.x` tokens INSIDE that block. This stops Receipt #3's row from leaking into Receipt #2's window (the earlier 600-char window approach could).

Forbidden tokens within ~120 chars of a negation/prohibition/future word (`not`, `never`, `future`, `roadmap`, `prohibited`, …) are allowed (explicit `Receipt #2 does NOT claim AU.L2-3.3.4` is fine).

### 4. Overclaim firewall

Substring/word-boundary scan across **all public HTML** — root `*.html`, `blog/*.html`, `proof/ir/*.html`, and `research/**/*.html` — for unsupported affirmative claim phrases:

```
signed, signature, Ed25519, certified, compliant, compliance proof,
customer evidence, production deployment, enclave, private key,
C3PAO approved, audit ready, tamper-evident, tamper detection,
unaltered, has not been altered, changed after it was created,
detects any tampering, tampered with after the fact
```

Short ambiguous phrases (`signed`, `certified`, `compliant`, `enclave`, `unaltered`, `signature`, `Ed25519`) are matched with word boundaries to avoid substring false positives like "designed", "GDPR-compliant". `<script>...</script>` and `<style>...</style>` blocks are masked before scanning (line numbers preserved).

**Allowed contexts are SENTENCE-SCOPED and CONCEPT-SPECIFIC.** A hit is allowed only if one of the rules below applies in the SAME sentence as the hit. Sentence boundaries split on `.`/`!`/`?`/`;` followed by whitespace, on inline HTML breaks (`<br>`), and on block-end tags (`</p>`, `</li>`, `</td>`, `</h*>`). Hedge words like `synthetic`/`demo`/`sample` no longer act as an across-sentence allower — that was the broad-window exploit the original review surfaced.

| # | Rule | Applies to | Examples |
| --- | --- | --- | --- |
| 1 | Explicit allowlist entry (file + phrase + line-substring + justification) | Any phrase | (currently empty) |
| 2 | Negation / prohibition in same sentence | All phrases | `not Ed25519-signed`, `does not certify`, `prohibited`, `withheld` |
| 3 | Roadmap qualifier in same sentence | All phrases | `Ed25519 signature on the roadmap`, `if and when`, `pre-assessment` |
| 4 | Contract noun in same sentence | `signed`, `signature` | `signed Master Services Agreement`, `signed SOW`, `signed amendment` |
| 5 | Possessive customer-owned enclave in same sentence | `enclave` | `Customer's enclave`, `your enclave`, `client's enclave`, `Customer-designated enclave` |
| 6 | HMAC-SHA256 in same sentence | `signed`, `signature` | `detached HMAC-SHA256 signature file` |
| 7 | Detection-signature domain term in same sentence | `signature` | `detection signatures`, `signature-only`, `stylometric signatures` |

To add a new exception, prefer adding a typed entry to `OVERCLAIM_ALLOWLIST` (in `scripts/release_gate.py`) with file + phrase + line-substring + justification, rather than broadening rules 2–7. Keep the list small and explicit.

Verifier banned-phrase arrays (the JS/Python `BANNED_PHRASES` literals in the verifier code) are handled by `<script>` masking — they are not user-visible claim text. There is NO generic "quoted-string list" allowance any more.

### 5. Link / surface

- `/verify.html#trust-ledger` anchor exists in `verify.html`.
- Every entry in `PUBLIC_RECEIPTS` exists as both `.json` and `.sha256` at the repo root, AND the sidecar's filename token names the correct receipt file.
- Every `href="...verify_standalone.py..."` in `verify.html` resolves to a file in the repo.

No external network access is required.

## Wiring

The workflow runs on:

- every push to `main`
- every pull request targeting `main`
- manual dispatch from the Actions UI

A failing gate marks the workflow as failed. **Branch protection on `main` is required to make this gate a real deploy block** — see "Honest framing on deploy-blocking" above for the exact configuration.

The `integrity-heartbeat.yml` workflow remains independent — it verifies the published bundle on hardseal.ai every 6 hours. The release gate verifies the source-of-truth in this repo before that bundle is built.

## Adversarial review checklist

Before merging changes that touch the gate itself:

- [ ] The gate still passes on the current repo state.
- [ ] All negative-fixture tests in `scripts/test_release_gate.py` still pass.
- [ ] No new structural exception broadens the allowed contexts beyond what is documented above. New exceptions go in `OVERCLAIM_ALLOWLIST` with file/phrase/pattern/justification.
- [ ] The new pattern is exercised by a negative-fixture test.
- [ ] Failure messages name the file path, line number, and the specific reason.

## Limitations / known gaps

- HTML scope is `*.html`, `blog/*.html`, `proof/ir/*.html`, and `research/**/*.html`. PDFs and downloadable archives (`.tar.gz`, `.zip`) are not scanned. If a public claim surface moves into one of those, extend `PUBLIC_HTML_GLOBS` and/or add an archive-specific check.
- The Receipt #2 mapping check is anchored to `verify.html`. If Receipt #2's mapping is asserted in additional public surfaces (e.g., trophy-case.html, blog posts), extend the check.
- The allowed-context rules are sentence-scoped. A hit and its qualifier must share a sentence; the gate will not catch a real overclaim whose negation/qualifier was deleted but whose sentence still happens to end with a contract noun. Mitigation: every new affirmative claim should ship with a `test_release_gate.py` case proving it is caught when its qualifier is removed.
- `detection signatures` (research/blog terminology) is whitelisted for `signature` only. A real cryptographic-signature overclaim that sits in a sentence containing the word `detection signatures` would slip through. Audited against current public surface — no false positives observed today.
- Pages legacy auto-build cannot be hard-blocked from this workflow alone. Branch protection on `main` is the necessary enforcement; see "Honest framing on deploy-blocking" above.
