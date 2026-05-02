# Public Proof Gate

Locked checklist that runs BEFORE any public claim post (LinkedIn, Twitter, blog, email send) about a Hardseal Edge release.

**No green check, no public post. Hard rule.**

Every box is a failure-mode that has surfaced at least once in a Hardseal release. Each box converts a past failure into a runnable test.

## Checklist

- [ ] Live bundle URL downloads (hardseal.ai/downloads/...)
- [ ] Live `.sha256` sidecar downloads, matches expected
- [ ] Computed `sha256` of downloaded zip matches expected
- [ ] Fresh unzip + standalone verifier returns `PASS` for the new packet
- [ ] Intentional one-byte tamper of any `packet.json` returns `FAIL`
- [ ] No stale v2.2 references on any public page
- [ ] No banned-phrase hits on the public surface
- [ ] No assessor-equivalence language
- [ ] No CMMC certification or assessor-readiness claims
- [ ] Claim ledger row (`PUBLIC_CLAIM_TRACE_LEDGER`) updated for the new release

## Reference commands (run these to fill the boxes)

```bash
# 1. Live bundle URL downloads
curl -fsSL -o /tmp/hardseal_edge_trophy_case.zip \
  https://hardseal.ai/downloads/hardseal_edge_trophy_case.zip

# 2. Live .sha256 sidecar downloads, matches expected
curl -fsSL -o /tmp/hardseal_edge_trophy_case.zip.sha256 \
  https://hardseal.ai/downloads/hardseal_edge_trophy_case.zip.sha256
cat /tmp/hardseal_edge_trophy_case.zip.sha256
# Expected format: <sha256>  hardseal_edge_trophy_case.zip

# 3. Computed sha256 of downloaded zip matches expected
shasum -a 256 /tmp/hardseal_edge_trophy_case.zip   # macOS
# OR
sha256sum   /tmp/hardseal_edge_trophy_case.zip     # Linux
# Expected: matches RELEASE_LEDGER.md row's Bundle SHA

# 4. Fresh unzip + standalone verifier returns PASS for the new packet
mkdir -p /tmp/hsverify && cd /tmp/hsverify
unzip -o /tmp/hardseal_edge_trophy_case.zip
cd trophy_case_bundle
python3 verify_standalone.py <NEW_PACKET_DIR>/packet.json
# Expected: ends with "result: PASS"

# 5. Intentional one-byte tamper of any packet.json returns FAIL
cp <NEW_PACKET_DIR>/packet.json /tmp/tampered.json
python3 -c "
import json
d = json.load(open('/tmp/tampered.json'))
d['benchmark']['mean_ms'] += 0.001
json.dump(d, open('/tmp/tampered.json','w'))
"
python3 verify_standalone.py /tmp/tampered.json
# Expected: FAIL (chain root mismatch)

# 6. No stale v2.2 references on any public page
curl -fsSL https://hardseal.ai/trophy-case.html | grep -Ei "11 packets|eleven packets|269 KB|f6fdc719"
# Expected: zero matches

# 7. No banned-phrase hits on the public surface
# Run scripts/guardrails_check.py from the canonical hardseal repo against:
#   - trophy-case.html
#   - index.html (homepage)
#   - edge.html
#   - verify.html
#   - resources.html
#   - any blog post or downloadable PDF linked from public pages
# Canonical list governs. Negation-context disclaimers are protective and pass.

# 8/9. No assessor-equivalence language / no CMMC certification / assessor-readiness claims
# Manual scan against the canonical doctrine in hardseal repo.

# 10. Claim ledger row updated
# Append a row in PUBLIC_CLAIM_TRACE_LEDGER (canonical doctrine, hardseal repo)
# referencing the matching RELEASE_LEDGER.md row before the post ships.
```

## Discipline

Public proof before public claims. Failure-to-test or it decays. Every gate that fires becomes a regression test, a release gate, or a doctrine update — not a Slack message.

If a box cannot be checked, the post does not ship. If a box was checked but a defect surfaced after the post shipped, the gate is updated to catch it next time, and the corresponding `RELEASE_LEDGER.md` row's `Known risks` column is amended.

## Continuous Attestation no-public-claim rule

Continuous Attestation is an **active implementation shipping in this release**, NOT a deferred commitment. The architecture compounds today AND the implementation runs today. The public CLAIM, however, still waits for receipts.

**Implementation status (locked 2026-05-02 PM ET):** GitHub Actions workflow `.github/workflows/integrity-heartbeat.yml` runs every 6 hours on GitHub's infrastructure. Downloads the live bundle from hardseal.ai, verifies SHA against the published sidecar plus every packet via the standalone verifier, appends a self-hash-chained heartbeat line to `docs/integrity/INTEGRITY_LOG.md`, commits + pushes via scoped `GITHUB_TOKEN`. 24/7 autonomous. No human in the loop. No conference-presence requirement.

**Public-claim rule (still locked, applies to claims NOT to implementation):** No homepage / trophy-case / pilot / blog / LinkedIn / Twitter / press / pitch / handout / verbal-conference-floor claim may state or imply continuous re-verification UNTIL `INTEGRITY_LOG.md` has at least 7 consecutive clean heartbeat entries (≥ 42 hours of receipts) live on hardseal.ai.

Until that floor is reached:

- ✅ The workflow runs autonomously — every 6 hours the heartbeat fires.
- ✅ Internal doctrine documents reference Continuous Attestation freely (this file, RELEASE_COMMANDER_CHECKLIST, BUNDLE_RELEASE_PROCEDURE).
- ❌ No customer-facing claim text references continuous re-verification, in any medium, until threshold.

**Activation event:** when the 7th consecutive clean heartbeat lands, the no-public-claim rule is removed (here and in BUNDLE_RELEASE_PROCEDURE_v2.md), public claims are greenlit, and an activation entry is filed in HARDSEAL_DAILY_LOG.md. See `docs/ops/RELEASE_COMMANDER_CHECKLIST_v2_3.md` section 5 for the full activation timeline and architecture pointer.

## Learning Loop 5-condition closure rule

A failure is not closed until all five conditions are met:

1. Named — a single sentence describing the failure mode in concrete terms.
2. Root cause identified — the underlying mechanism, not the symptom.
3. Prevention mechanism created — a regression test, release gate, or doctrine update.
4. Prevention mechanism tested on a real run — exercised against actual artifacts, not paper-checked.
5. Doctrine or checklist updated — the prevention is wired into the path future releases walk.

No "we learned from it" hand-waving. The proof gate enforces this discipline: a failure that is not closed under all five conditions cannot have its row marked complete in `RELEASE_LEDGER.md`'s `Known risks` column.

## Proof Half-Life metric

**Proof Half-Life:** how long can a public Hardseal claim remain verifiable without human explanation?

- Signed evidence packet → years.
- Continuous attestation log → forever-while-running.
- Unverifiable adjective / future-tense claim / unscoped superlative → NEGATIVE proof half-life. Decays the moment a skeptic asks "prove it."

This is Hardseal's moat measurement. Every public artifact is designed to maximize proof half-life. Every claim that lowers it is rewritten or removed before publication.

The proof gate's role is to refuse public-claim posts whose proof half-life is negative.
