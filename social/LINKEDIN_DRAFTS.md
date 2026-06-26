# Hardseal Edge — LinkedIn drafts & posting engine

Receipts over claims. Every number below recomputes from public bytes. Do not
post a metric that isn't in a sealed packet. To mint a fresh card from any run:

```
python3 scripts/post_card.py <path-to-packet.json>
```

It refuses to emit a card unless the chain root recomputes **and** the shipped
verifier returns `result: PASS`. The generator holds the same line the product
does.

Numbers in these drafts verified from the live bundle on 2026-06-24:
bundle `18c135af…`, verifier `103fb99c…`, 12/12 chain roots recompute.

---

## Lead post (pin this)

I don't ask you to trust the numbers.
I hand you the bytes so you can verify them yourself.

Every Hardseal benchmark is sealed in tamper-evident evidence packets. Download
the bundle, read the verifier, recompute the roots. If a single byte changed, it
fails.

**Here's what you can prove today** — straight from public packets anyone can inspect:

1. **12 sealed evidence packets** from a real Jetson Orin Nano Super. All 12 chain roots recompute and match. Bundle: `18c135af…` • Verifier: `103fb99c…`
2. **13.23-hour endurance soak** — 2,000,000 inferences, YOLOv8x INT8/TensorRT, 25W pinned clocks, mean 23.81 ms, p99 39.23 ms, ~42 FPS. Sealed in one packet.
3. **Million-inference speed run** — 293 FPS (YOLOv8n INT8, mean 3.41 ms). Also sealed and reproducible.
4. **Zero-dependency stdlib-only verifier** (read it before you run it). 8 pass-gates + an active banned-phrase scan that kills the bundle if it contains legal overclaims. The tool polices Hardseal's own language.
5. **177 consecutive clean integrity checks** (~44 days). 214 total. 6 historical FAILs published, never hidden. Every 6 hours a robot re-downloads the bundle and re-runs the full verifier on a hash-chained log you cannot quietly edit.
6. **Today's receipt**: we caught our own website claiming sealed power data the packets don't contain — and fixed it in public.

The category nobody else occupies: everyone else posts cherry-picked model names
and best-case FPS. We post dated, cryptographically verifiable evidence from real
silicon — and re-verify + publish our own failures every six hours.

Trophy case: https://hardseal.ai/trophy-case.html
Verifier: https://hardseal.ai/verify.html

---

## Post A — the challenge

Most edge-AI benchmark posts say "trust me." Here's the opposite.

12 sealed evidence packets from a real Jetson Orin Nano Super, each carrying its
own SHA-256 chain root.

Download the bundle → read the 400-line Python stdlib verifier (no pip, no
network) → run it → recompute every root yourself.

If one byte was altered, the entire bundle fails.

Don't trust me. Verify me.
https://hardseal.ai/trophy-case.html

#EdgeAI #VerifiableAI #ReceiptsNotClaims

---

## Post B — the endurance receipt

13.23 hours. 2,000,000 inferences. One Jetson Orin Nano Super at 25W with clocks pinned.

YOLOv8x INT8 on TensorRT: mean 23.81 ms, p99 39.23 ms, ~42 FPS.

All of it sealed into a single tamper-evident packet whose root is published.
Honest scope is declared inside the packet itself: synthetic input, single
device, bench conditions.

Recompute it yourself.
https://hardseal.ai/trophy-case.html

---

## Post C — the self-verifier

177 consecutive automated integrity checks passed. Every 6 hours, for 44 straight
days, a robot re-downloads the live bundle and re-runs the full verifier.

We've also published 6 FAILs in the open. A verification company that hides its
own failures is just another vendor.

The log is hash-chained — you cannot edit the past without breaking the present.
https://hardseal.ai/docs/integrity/INTEGRITY_LOG.md

---

## The 2–3×/week engine that never runs dry

Tie every post to the machine itself:

- **Every new run/packet → 1 "Receipt" post** — run `scripts/post_card.py` on the new packet, paste the output.
- **Once a week → 1 "Heartbeat" post** — streak update, or (best of all) a published FAIL.
- **Occasionally → 1 "Build-in-Public" post** — the exact claim-vs-bytes fix, power-sealing progress, etc.

Three lanes. 2–3 posts/week, indefinitely, nothing invented.

Discipline for every post: real numbers, declared limitations, no "certified," no
sealed-power claim until that field actually ships.
