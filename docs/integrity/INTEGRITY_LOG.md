# Hardseal Edge Integrity Log

This log is appended to autonomously by `.github/workflows/integrity-heartbeat.yml`
running on GitHub Actions every 6 hours. Each line is a heartbeat: a receipt that
the live `hardseal_edge_trophy_case.zip` at https://hardseal.ai/downloads/ matches
its published `.sha256` sidecar and that every packet inside passes
`verify_standalone.py`.

This file is **machine-generated**. Do not hand-edit. The `guardian_sha` field on
each line is `sha256(previous_full_line || current_line_minus_guardian_sha)`,
chaining each entry to the previous one. Any retroactive edit to a past entry
will break the chain at every entry that follows. The chain is the proof.

## Schema

Every heartbeat line:

`<UTC timestamp> | bundle_sha=<observed> | bundle_bytes=<observed> | packets=<pass>/<total> | result=<PASS|FAIL> | verifier_sha=<sha> | guardian_sha=<sha> | next=<UTC+6h>`

- `bundle_sha` — sha256 of the live bundle as fetched in this heartbeat.
- `bundle_bytes` — wc -c of the live bundle.
- `packets` — pass count over total count, after running the standalone verifier
  inside the unpacked bundle.
- `result` — PASS only if the bundle downloaded, the sidecar matched, and every
  packet passed. Otherwise FAIL.
- `verifier_sha` — sha256 of `verify_standalone.py` shipped inside the bundle.
  Bit-identical across releases per Amendment 3.
- `guardian_sha` — self-hash chain over all prior content. Tamper-evident.
- `next` — when the next heartbeat is expected.

## No-public-claim rule (locked)

No public homepage / trophy-case banner / pilot pitch / blog / LinkedIn / Twitter /
press / email / handout / verbal-conference-floor claim may state or imply that
Hardseal continuously re-verifies its bundles UNTIL this log has at least 7
consecutive clean heartbeat entries (≥ 42 hours of receipts) live on hardseal.ai.

The implementation runs immediately on PR merge. The public claim waits for
receipts. See `docs/ops/RELEASE_COMMANDER_CHECKLIST_v2_3.md` section 5 for the
full activation timeline and allowlist of permitted private references.

## FCA-flank disclaimer

This log is integrity attestation, not regulatory certification. Heartbeat PASS
does not certify CMMC compliance, FAA airworthiness, or any other regulatory
outcome. The bundle's evidence packets carry the same separation between
integrity evidence and certification claim — see the `limitations` section in
each `packet.json`. The integrity log proves that the bundle on hardseal.ai
right now is bit-identical to the bundle Hardseal published; it does not prove
anything about regulatory acceptance.

## FAIL is publishable

When a heartbeat detects a real failure, the FAIL line is committed to this log
anyway, then the workflow run exits non-zero. The failure publishes. That is
the trust signal.

# CHAIN_ANCHOR seed=hardseal-edge-integrity-log-v1
