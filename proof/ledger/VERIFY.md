# Verify the time-in-production ledger

This directory contains the published time-in-production receipt ledger plus an independent timestamp anchor. Anyone can re-derive the chain root and verify the timestamp without trusting us, GitHub, or any CA.

## Files

| File | What it is |
|---|---|
| `ledger.jsonl` | The full hash-chained receipt ledger (one JSON object per line). |
| `LEDGER_ROOT.txt` | The chain root: the SHA-256 head of the chain over all entries in `ledger.jsonl`. |
| `LEDGER_ROOT.txt.ots` | An OpenTimestamps proof that `LEDGER_ROOT.txt` existed at a specific moment, anchored into Bitcoin via the OTS calendar network. |

## What each check proves

- **Chain recomputation** proves that `ledger.jsonl` is internally consistent and that `LEDGER_ROOT.txt` is the correct head — i.e., no entry has been silently changed or reordered.
- **OpenTimestamps verification** proves that `LEDGER_ROOT.txt` (with that exact byte content) existed *no later than* the Bitcoin block referenced in the `.ots` proof. The witness is the Bitcoin chain, not us.

These checks together establish: the published receipt ledger is consistent with the published root, and that root was committed to an external public record at a verifiable point in time. They do **not** prove that any individual receipt's underlying claim is true; they prove the receipts have not been edited or post-dated.

## Recompute the chain root yourself

The ledger is a simple SHA-256 chain over JSONL entries. Any implementation that walks `ledger.jsonl` and computes the documented chain function will produce the same root. The reference implementation lives at `time_in_production_ledger/ledger.py` (separate distribution); a self-contained verifier is in scope for the public `verify-kit`.

Expected output from the reference implementation:

```
$ python3 ledger.py verify
OK  N entries, chain intact.
ledger_root: <hex matches LEDGER_ROOT.txt>
```

## Verify the OpenTimestamps proof

Install once (Python or Node):

```
pip install --user opentimestamps-client
# or: npm install -g opentimestamps
```

Then, in this directory:

```
ots upgrade LEDGER_ROOT.txt.ots   # pulls the Bitcoin attestation once a block has confirmed
ots verify  LEDGER_ROOT.txt.ots   # checks the proof end-to-end against Bitcoin
```

A passing `ots verify` reports the earliest Bitcoin block height that contains a commitment to the SHA-256 of `LEDGER_ROOT.txt`. That block's timestamp is the earliest moment the root provably existed.

A freshly submitted proof shows `PendingAttestation` from each calendar until a Bitcoin block is mined that includes the calendar's aggregated commitment (typically within an hour). Until then, `ots upgrade` will report that no Bitcoin attestation is available yet and `ots verify` will not produce a block-height result. The calendar's pending receipt is itself an independent witness; the Bitcoin attestation is the offline-checkable form.

## The claim this supports (firewall-clean wording)

> Our receipt ledger is published to a dated public record, and the ledger root is independently timestamped against Bitcoin. Recompute the chain and verify the `.ots` offline. We cannot have produced the Bitcoin attestation after the block in which it was included.

This intentionally does not say "tamper-proof", "tamper-evident", "unaltered", or any certify / compliant / assessor language. The strength is the external timestamp; we say exactly that.
