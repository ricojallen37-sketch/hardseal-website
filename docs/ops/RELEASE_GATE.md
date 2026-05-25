# Release Gate

Public-proof honesty gate that runs before public deploy. If a public page, verifier, receipt, sidecar, or Trust Ledger claim drifts, the site should not deploy.

**Script:** `scripts/release_gate.py` — standard library only, <1s on the current repo.
**Tests:** `scripts/test_release_gate.py` — negative-fixture suite proving the gate catches each documented failure mode.
**CI:** `.github/workflows/release-gate.yml` — runs on every push to `main` and every PR targeting `main`.

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
- If `downloads/verify_standalone.py` (or `proof/ir/verify_standalone.py`) is present, the verifier is invoked on Receipt #1 and must print `result: PASS`.

The gate never mutates packet JSON. Receipt #1 is the only packet the verifier is run against in the gate path (the full bundle verifier loop already runs in `integrity-heartbeat.yml` against the live bundle).

### 2. Trust Ledger labeling

Checks `verify.html`:

- The Trust Ledger must be labeled as `Receipts #1-#4 · Index` (or equivalent — ASCII `-`, en/em dash, or `to` are accepted; `Index` or `Ledger` are accepted).
- The Trust Ledger must NOT be labeled or implied as Receipt #5. The next packet receipt being numbered #5 in a future release is fine; the *ledger itself* is an index, not a receipt.

### 3. Receipt #2 mapping

Receipt #2 maps to:

- `AU.L2-3.3.1`
- `AU.L2-3.3.2`
- `AU.L2-3.3.8`

Any appearance of `AU.L2-3.3.3` through `AU.L2-3.3.7` as a Receipt #2 mapping claim fails the gate. The gate looks at every `AU.L2-3.3.x` token in `verify.html` and inspects a ~600-char window before it for a "Receipt #2" anchor; only tokens inside that anchored context are treated as Receipt #2 claims. Forbidden tokens within ~120 chars of a negation/prohibition/future word (`not`, `never`, `future`, `roadmap`, `prohibited`, …) are allowed.

### 4. Overclaim firewall

Substring/word-boundary scan of all public HTML files (`*.html` at the repo root) for unsupported affirmative claim phrases:

```
signed, signature, Ed25519, certified, compliant, compliance proof,
customer evidence, production deployment, enclave, private key,
C3PAO approved, audit ready, tamper-evident, tamper detection,
unaltered, has not been altered, changed after it was created,
detects any tampering, tampered with after the fact
```

Short ambiguous phrases (`signed`, `certified`, `compliant`, `enclave`, `unaltered`, `signature`, `Ed25519`) are matched with word boundaries to avoid substring false positives like "designed", "GDPR-compliant".

**Allowed contexts** (a hit in any of these is not a failure):

1. **Explicit allowlist** — an entry in `OVERCLAIM_ALLOWLIST` (file + phrase + line-substring + justification). Currently empty.
2. **HMAC-SHA256 factual reference** — relaxes only `signed`/`signature` when the line mentions `HMAC-SHA256`.
3. **Banned-phrase array literal** — short standalone quoted-string lines, or single-line arrays dominated by comma-separated quoted strings. This recognizes the verifier's `BANNED_PHRASES` arrays in JS/Python.
4. **Negation / prohibition / roadmap qualifier nearby** — `not`, `no`, `never`, `prohibited`, `forbidden`, `future`, `roadmap`, `planned`, `if and when`, etc., within ~250 chars before the hit.
5. **Contract context** (`signed`/`signature` only) — `agreement`, `MSA`, `SOW`, `Subscription Order`, `engagement`, etc. nearby. "Signed Master Services Agreement" is a signed legal document, not a signed Hardseal artifact.
6. **Customer-owned environment** (`enclave` only) — `customer's`, `client's`, `customer-designated`, etc. nearby. "Customer's enclave" is a factual reference to the customer's infrastructure, not a claim that Hardseal operates one.
7. **Hedge qualifier nearby** — `synthetic`, `demo`, `demonstration`, `sample`, `example`, `illustrative`, `assessor-readable`, `integrity demonstration`, `replay artifact`. The honesty/proof-IR sweep added these qualifiers around residual claim language; the gate respects them.

`<script>...</script>` and `<style>...</style>` blocks are masked before scanning (line numbers preserved). They are not user-visible claim text.

To add a new exception, prefer adding an entry to `OVERCLAIM_ALLOWLIST` with a clear justification rather than broadening the structural rules. Keep the list small and explicit.

### 5. Link / surface

- `/verify.html#trust-ledger` anchor exists in `verify.html`.
- Every entry in `PUBLIC_RECEIPTS` exists as both the JSON and the `.sha256` sidecar at the repo root.
- Every `href="...verify_standalone.py..."` in `verify.html` resolves to a file in the repo.

No external network access is required.

## Wiring

The workflow runs on:

- every push to `main`
- every pull request targeting `main`
- manual dispatch from the Actions UI

A failing gate marks the workflow as failed. To block merges, configure branch protection on `main` to require the `release-gate / gate` check.

The `integrity-heartbeat.yml` workflow remains independent — it verifies the published bundle on hardseal.ai every 6 hours. The release gate verifies the source-of-truth in this repo before that bundle is built.

## Adversarial review checklist

Before merging changes that touch the gate itself:

- [ ] The gate still passes on the current repo state.
- [ ] All negative-fixture tests in `scripts/test_release_gate.py` still pass.
- [ ] No new structural exception broadens the allowed contexts beyond what is documented above. New exceptions go in `OVERCLAIM_ALLOWLIST` with file/phrase/pattern/justification.
- [ ] The new pattern is exercised by a negative-fixture test.
- [ ] Failure messages name the file path, line number, and the specific reason.

## Limitations / known gaps

- Only `*.html` at the repo root is scanned for overclaims. Blog posts (`blog/*.html`), policy pages under subdirectories, and PDFs are out of scope today. If a public surface moves outside the repo root, extend `PUBLIC_HTML_GLOBS`.
- The Receipt #2 mapping check is anchored to `verify.html`. If Receipt #2's mapping is asserted in additional public surfaces (e.g., trophy-case.html, downloadable PDFs), extend the check.
- The standalone verifier is invoked only on Receipt #1. Full-bundle verification continues to be the integrity-heartbeat workflow's job.
