<!--
Upstream source: Mastering Edge A.I/RELEASE_COMMANDER_CHECKLIST_v2_3.md (Cowork Claude workspace draft).
This file is the team-facing mirror. Cowork folds the additional workspace-draft sections in a follow-up commit.
TODO: Cowork to fold workspace draft content
-->

# Release Commander Checklist — v2.3 conference publish

The single cockpit for the v2.3 conference publish. Tracks PR order, the public proof gate, stop conditions, and the three doctrine rules that govern public claims. All other Release Factory artifacts (`RELEASE_LEDGER.md`, `PUBLIC_PROOF_GATE.md`, `AI_AGENT_SCOREBOARD.md`) feed into this checklist; this checklist gates the public claim.

The finish line is NOT the merge. The finish line is:

- Live download verifies `PASS`
- Tamper verifies `FAIL`
- Zero stale references on public surfaces
- `PUBLIC_CLAIM_TRACE_LEDGER` row appended

## PR order (locked)

Merge in this order. PR #1 is independent and may land at any time. PR #4 is independent of the publish flow.

1. **PR #3** (`push-7-chain-roots` → `main`, hardseal-website) — chain-root rows + narrative paragraph + word-form-number stale-prose + Release Factory v1 docs (`RELEASE_LEDGER.md`, `PUBLIC_PROOF_GATE.md`, this commander checklist).
2. **PR #2** (`bundle-v2.3` → `main`, hardseal-website) — bundle binary swap, line 70 metadata line, line 71 `bundle_sha256`, sidecar `.sha256` file at `/downloads/hardseal_edge_trophy_case.zip.sha256`.
3. **PR #1** (`revamp-2026` → `main`, hardseal-website) — homepage revamp. Independent of bundle release; can land before, between, or after.
4. **PR #4** (`hardseal-ai-ops`, `command-bridge/learning/AI_AGENT_SCOREBOARD.md`) — opens after PR #3 lands clean. Independent of the publish flow. Rico merges PR #4 separately.

Order rationale: PR #3 first preserves the line-70/71 atomic SHA-and-bundle pair across the merge window. The chain-root rows for v2.3 packets land before the v2.3 bundle does — confusing but not corrupt. The inverse order (PR #2 first) would leave the chain-root table referencing v2.2-only packets while line 71 already points at the v2.3 SHA — the bundle SHA pair would be atomically consistent but the chain-root display would lag the bundle's contents. Both windows are bounded; PR #3-first keeps the SHA/bundle pair atomic at all times, which is the load-bearing invariant.

## Stop conditions

Halt and surface; do not proceed with later steps if any of these fire.

- [ ] Banned-phrase scan returns any hit on the canonical list (`scripts/guardrails_check.py` in hardseal repo) for any text-bearing file in the diff.
- [ ] Read-back of any chain-root prefix fails to decode as `^[0-9a-f]{8}$` lowercase hex.
- [ ] Any value on the page is editorial rather than bundle-derived.
- [ ] Live bundle URL fails to download after PR #2 merges.
- [ ] Live `.sha256` sidecar mismatches expected after PR #2 merges.
- [ ] Computed `sha256` of downloaded zip mismatches expected after PR #2 merges.
- [ ] Standalone verifier returns anything other than `result: PASS` on any new packet after PR #2/#3 merge.
- [ ] One-byte tamper test returns anything other than `FAIL` after PR #2/#3 merge.
- [ ] Any stale v2.2 reference (`11 packets` / `eleven packets` / `269 KB` / `f6fdc719`) survives on any public page after PR #3 merge.

## Public proof gate (PR #2 + PR #3 must both have merged)

Run the reference commands in `PUBLIC_PROOF_GATE.md`. Tick every box. Then and only then is a public claim eligible to ship.

- [ ] Live bundle URL downloads (hardseal.ai/downloads/hardseal_edge_trophy_case.zip)
- [ ] Live `.sha256` sidecar downloads, matches expected
- [ ] Computed `sha256` of downloaded zip matches expected (`18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce`)
- [ ] Fresh unzip + standalone verifier returns `PASS` on `yolov8x_8hr_sustained_25W_20260501T203554Z/packet.json`
- [ ] Standalone verifier returns `PASS` on the three new yolov8x MAXN replicate packets
- [ ] Intentional one-byte tamper of any `packet.json` returns `FAIL`
- [ ] No stale v2.2 references on any public page
- [ ] No banned-phrase hits on the public surface
- [ ] No assessor-equivalence language
- [ ] No CMMC certification or assessor-readiness claims
- [ ] `PUBLIC_CLAIM_TRACE_LEDGER` row appended for the new release
- [ ] `RELEASE_LEDGER.md` v2.3 row's `Cold verify result` flipped from `pending` to `PASS`
- [ ] `RELEASE_LEDGER.md` v2.3 row's `Tamper result` flipped from `pending` to `FAIL`

## 5. Continuous Attestation rule (locked, IMPLEMENTATION SHIPPING NOW)

**As of 2026-05-02 PM ET (Rico doctrine override — "we don't defer to post-conference"):** Continuous Attestation is an **active implementation shipping in this release**, NOT a deferred commitment. The architecture compounds. The implementation runs. The public claim STILL waits for receipts.

**Implementation:** GitHub Actions workflow `.github/workflows/integrity-heartbeat.yml` in the hardseal-website repo, drafted by Cowork at `Mastering Edge A.I/INTEGRITY_HEARTBEAT_WORKFLOW_DRAFT.yml`, staged by Perplexity into PR #3 scope. Runs every 6 hours. Downloads live bundle from hardseal.ai, verifies SHA against sidecar + every packet via standalone verifier, appends self-hash-chained heartbeat line to `docs/integrity/INTEGRITY_LOG.md`, commits + pushes via scoped GITHUB_TOKEN. 24/7 autonomous on GitHub's infra. Survives Rico's Maryland travel.

**Activation timeline (the 42-hour clock starts on PR merge):**

| Heartbeat # | Approx. timestamp (ET) | Event |
|---|---|---|
| 1 | Saturday 2026-05-02 (on PR #3 merge, immediate via push trigger) | First heartbeat fires |
| 2 | ~6 hours later | Second heartbeat (cron `0 */6 * * *`) |
| ... | ... | ... |
| 7 | Monday 2026-05-04 ~AM ET | **Public claim activation threshold met** |

**Hard rule (still locked, applies to public claim NOT to implementation):**

> No public homepage / trophy-case / pilot / blog / LinkedIn / Twitter / press / pitch / email / conversation / handout / verbal-conference-floor-claim may state or imply that Hardseal continuously re-verifies its bundles UNTIL `INTEGRITY_LOG.md` has at least 7 consecutive clean heartbeat entries (≥ 42 hours of receipts) live on hardseal.ai.

**What's allowed in the meantime:**

- ✅ **Workflow runs autonomously** — every 6 hours the heartbeat fires and the log accumulates.
- ✅ **Internal AI agent + Cowork doctrine references** — Continuous Attestation is built into RELEASE_COMMANDER_CHECKLIST, BUNDLE_RELEASE_PROCEDURE (forthcoming, queued for Cowork follow-up), memory entries.
- ✅ **Whisper to a sophisticated CISO during a private 1-on-1** — "we just shipped continuous attestation, the cron is running, you can watch the log accumulate at hardseal.ai/integrity-log" — that's not a marketing claim, that's an honest invitation to verify.
- ❌ Homepage / trophy-case UI banner claiming continuous attestation = blocked until threshold.
- ❌ LinkedIn Post 1 referencing continuous attestation = blocked until threshold.
- ❌ Conference handout referencing continuous attestation = blocked until threshold.

**Activation event:** when 7th consecutive clean heartbeat lands in INTEGRITY_LOG.md, Cowork:
1. Verifies the chain: every guardian_sha matches expected (no log tampering).
2. Removes the no-public-claim rule from this checklist + BUNDLE_RELEASE_PROCEDURE_v2.md (forthcoming, queued for Cowork follow-up).
3. Greenlights public claims referencing continuous attestation (homepage UI, LinkedIn future posts, conference verbal pitch).
4. Files an entry in HARDSEAL_DAILY_LOG.md (forthcoming, queued for Cowork follow-up) marking the activation moment.

**Architecture lives at:** `docs/architecture/CONTINUOUS_ATTESTATION_DESIGN.md` (hardseal repo, committed 2026-05-02 PM ET, hardened to reflect implementation-shipping-now).

**Why ship-now beats defer-to-post-conference:** by the time we walk into Maryland Monday morning, the heartbeat has been running 42+ hours. Competitors cannot backdate elapsed proof-time. Every hour the cron runs is an hour no one can match. Conference T-2 is the START of the moat clock, not the end of the deferral. *"We get shit done that takes years in days, then we refine and make it better."*

## 6. Learning Loop 5-condition closure rule

A failure is not closed until all five conditions are met:

1. Named — a single sentence describing the failure mode in concrete terms.
2. Root cause identified — the underlying mechanism, not the symptom.
3. Prevention mechanism created — a regression test, release gate, or doctrine update.
4. Prevention mechanism tested on a real run — exercised against actual artifacts, not paper-checked.
5. Doctrine or checklist updated — the prevention is wired into the path future releases walk.

No "we learned from it" hand-waving.

## 7. Proof Half-Life metric

**Proof Half-Life:** how long can a public Hardseal claim remain verifiable without human explanation?

- Signed evidence packet → years.
- Continuous attestation log → forever-while-running.
- Unverifiable adjective / future-tense claim / unscoped superlative → NEGATIVE proof half-life. Decays the moment a skeptic asks "prove it."

This is Hardseal's moat measurement. Every public artifact is designed to maximize proof half-life. Every claim that lowers it is rewritten or removed before publication.

## Operating doctrine

Massive action is not doing more. Massive action is making every rep permanently raise the floor. Public proof before public claims. Architecture claims stay internal until implemented. Quantity only matters when it improves future quality. Diligent, not frantic. Fast, not loose.
