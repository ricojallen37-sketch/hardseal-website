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
2026-05-02T17:19:21Z | bundle_sha=f6fdc719edc303eae774177f265fe86c6a55162c73d2540b5626ab58189ce7c9 | bundle_bytes=276471 | packets=0/11 | result=FAIL | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=ff48afe52382a72dc574ad5c97af0b6ec09f88180dc7013141575eed88c0ece6 | next=2026-05-02T23:19:22Z
2026-05-02T17:19:36Z | bundle_sha=f6fdc719edc303eae774177f265fe86c6a55162c73d2540b5626ab58189ce7c9 | bundle_bytes=276471 | packets=0/11 | result=FAIL | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=a71d9c95ec4784f020052945a1d35712605a84a4b080164dff878f2fc77a948b | next=2026-05-02T23:19:38Z
2026-05-02T19:10:28Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=0/12 | result=FAIL | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=06e5cd99410bf5888e6b3339dd232641ec9f24269cb2db299b33bcffde22116a | next=2026-05-03T01:10:29Z
2026-05-02T19:43:09Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=0/12 | result=FAIL | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=5f0985ba12be9f23a0290b9f8e42f0896248e75cf26f15b5715d09e901730b3f | next=2026-05-03T01:43:11Z
2026-05-02T20:29:13Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=112719e6becd54b981b5672607ef826e81536549edae98af28d3f88254c0ca69 | next=2026-05-03T02:29:14Z
2026-05-03T03:51:59Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=287cd714ef794874bd27b152e7f532b7f4403693bfd67e7753e98c8bb57ee0e7 | next=2026-05-03T09:52:00Z
2026-05-03T08:08:10Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=9429c9c5791bb08a4c6240acc56404009eadd738c4806589687c69fde6fafa00 | next=2026-05-03T14:08:13Z
2026-05-03T13:25:07Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=a5f77442a7873844b9d55f6cda423d31c45b8e07e8cdd761cde4b970dc62cfe4 | next=2026-05-03T19:25:09Z
2026-05-03T19:09:06Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=2d01ae5409912722ce7f7f7dac26323b2cbc9d8c5750784a6c6665286151afad | next=2026-05-04T01:09:07Z
2026-05-04T03:50:00Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=912d3e0029b9d5f546a8dc190c21c2d25f9e66f6d8ca7bdbdbd3cd32339e0b68 | next=2026-05-04T09:50:02Z
2026-05-04T08:38:09Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=32a4a606a281a818ed0a54774ef61932e3c2ed7f6cad21772c1e0bdfec02cc76 | next=2026-05-04T14:38:11Z
2026-05-04T14:18:37Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=6662716ecf1475b30126bc142bf23c696573441e8b7fba3b671d5071a64d56c1 | next=2026-05-04T20:18:39Z
2026-05-04T19:49:09Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=355ee8ca798c72342377563996d187c77bf9625f50e1b624ed87c62a36dd50da | next=2026-05-05T01:49:11Z
2026-05-05T03:32:08Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=95cad52e66801f04d0af29c386f05b545bd3abb307738aa1a94b58689fe6a8b6 | next=2026-05-05T09:32:09Z
2026-05-05T08:20:27Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=eb5be1345aa3855d9287c2398ac0c605eb9f0d51da61c6b34adee3306c60cdfd | next=2026-05-05T14:20:29Z
2026-05-05T14:11:20Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=9eba968b35205134677df219f10bd4ed11702afbe1e5d32d4dae0434f2ccb044 | next=2026-05-05T20:11:21Z
2026-05-05T19:43:44Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=47769af5a0dee077fe1243a3dfb3f5eba3b83436b09df15fce26f0afb764a6fd | next=2026-05-06T01:43:46Z
2026-05-06T03:45:47Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=59a9b096d64a166ed7c55497d64ac0cbf5a75233db90573aeba11600a191932c | next=2026-05-06T09:45:48Z
2026-05-06T14:30:41Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=d5dd3f917a98246f0cc5ee2edd27a798bce6e7790e75215c52564f5ea2ed46ef | next=2026-05-06T20:30:42Z
2026-05-06T19:54:02Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=1a0ecce443cf32df763ea2eca0223999d2b00a9d3617c643dee0976979ffecfa | next=2026-05-07T01:54:03Z
2026-05-07T03:44:40Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=945ea6fdb074e174cf187b47dc98aed0e8eb90d9a9ec58f0c0ed2880fb3a17d4 | next=2026-05-07T09:44:42Z
2026-05-07T08:43:08Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=55e9faaf3ec674f8f120e7df0c154a8d20a0458fbf898b65561b89ac388fd54f | next=2026-05-07T14:43:10Z
2026-05-07T14:31:55Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=de051951fcaeaf17cfc31e7d04cdf220e6ac54dc552d80c36798d95a6cce0d5c | next=2026-05-07T20:31:57Z
2026-05-07T19:48:32Z | bundle_sha=18c135af155114cf7137105b49446937a6fd234d660372e1b8839e4cf339cbce | bundle_bytes=302201 | packets=12/12 | result=PASS | verifier_sha=103fb99c0afc02ede89f25984b77051f4f45a7cfb446b203189169579c06320c | guardian_sha=55c4d957512c52576dec3db296c08e72631c0c0f67b3fece0b02695c97dfcf12 | next=2026-05-08T01:48:33Z
