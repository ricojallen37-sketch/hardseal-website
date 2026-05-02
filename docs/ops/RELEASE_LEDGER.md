# Hardseal Release Ledger

The audit spine for every Hardseal Edge trophy-case bundle release. One row per release. Every future release adds one row at release time. Non-deterministic fields (cold-verify result, tamper result, LinkedIn post URL) are filled by Rico after the Public Proof Gate runs green.

The row is the public proof of a release — read top-to-bottom, every value is mechanically traceable to bundle bytes (or marked `pending` / `n/a — pre-ledger`).

| Release | Date | Source repo commit | Website branch / PRs | Bundle SHA | Bundle bytes | Packet count | Chain root | Verifier SHA | Public URL | Cold verify result | Tamper result | Claim ledger row | LinkedIn post URL | Known risks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v2.3 | 2026-05-02 | ricojallen37-sketch/hardseal@2913a14 | hardseal-website: bundle-v2.3 (PR #2) + push-7-chain-roots (PR #3) | `18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce` | 302201 | 12 | `2a3acd739a422492d337f549949c2635a6d026ffb90a0b92c3103d01655a4fc5` | `103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c` | https://hardseal.ai/downloads/hardseal_edge_trophy_case.zip | pending | pending | pending | pending | SHA-stale-window between PR #3 and PR #2 merge — mitigated by Order A (PR #3 → PR #2 → PR #1, see PR #3 body) |
| v2.2 | n/a — pre-ledger | n/a — pre-ledger | n/a — pre-ledger | `f6fdc719edc303eae774177f265fe86c6a55162c73d2540b5626ab58189ce7c9` | 276471 | 11 | n/a — pre-ledger | `103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c` | https://hardseal.ai/downloads/hardseal_edge_trophy_case.zip | n/a — pre-ledger | n/a — pre-ledger | n/a — pre-ledger | n/a — pre-ledger | back-filled 2026-05-02 — pre-Release-Factory artifact, only deterministic fields recoverable |

## Field semantics

- **Release** — version tag (vMAJOR.MINOR). Increments per bundle change.
- **Date** — UTC release date.
- **Source repo commit** — `<repo>@<short-sha>` of the build commit in the canonical Hardseal Edge source repo. Not the website repo.
- **Website branch / PRs** — list every PR that ships this release on the storefront repo.
- **Bundle SHA** — `sha256` of `hardseal_edge_trophy_case.zip` exactly as published. Lowercase hex. Backticks for monospace.
- **Bundle bytes** — `wc -c` of the published `.zip`.
- **Packet count** — number of `packet.json` files inside the bundle.
- **Chain root** — chain root of the latest packet in the bundle (the trust anchor for newly added evidence). For v2.3 this is `yolov8x_8hr_sustained_25W_...`.
- **Verifier SHA** — `sha256` of `verify_standalone.py` shipped inside the bundle. Bit-identical across releases per Amendment 3.
- **Public URL** — live URL where the bundle downloads. Stable across releases; payload changes.
- **Cold verify result** — Rico runs the post-merge verification commands from a clean machine after merge. Must read `PASS` to flip the Public Proof Gate.
- **Tamper result** — Rico runs the one-byte tamper test from `PUBLIC_PROOF_GATE.md` item 5. Must read `FAIL` (verifier rejects tampered packet).
- **Claim ledger row** — corresponding row identifier in `PUBLIC_CLAIM_TRACE_LEDGER` (canonical doctrine, hardseal repo) for any public claim made about this release.
- **LinkedIn post URL** — only filled after the post ships and the gate flipped green.
- **Known risks** — release-specific risks: stale-window classes, integration concerns, deferred hand-offs.

## Discipline

Every row is the audit spine. No public claim about a release ships before its row is populated through `Cold verify result` and `Tamper result`. If a release row carries a `pending` in either of those columns, the Public Proof Gate fails — no LinkedIn post, no Twitter, no email send.

`n/a — pre-ledger` is reserved for back-filled rows captured before the Release Factory existed. Future releases do not get to use it.
