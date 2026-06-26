#!/usr/bin/env python3
"""
verify_chain.py — independently re-derive and verify the Hardseal integrity chain.

What this proves
----------------
docs/integrity/INTEGRITY_LOG.md is an append-only log of integrity heartbeats.
Each line carries a `guardian_sha` that chains it to the line before it:

    guardian_sha = sha256( previous_full_line || current_line_without_guardian_sha )

The first heartbeat chains to the `# CHAIN_ANCHOR` seed line. Because every
entry's hash depends on the entire entry before it, altering ANY past line
changes its hash and breaks every `guardian_sha` that follows. You cannot
backdate, reorder, delete, or edit history without the break becoming visible.

This script re-derives the whole chain from scratch and reports, per line and
overall, whether it holds. It depends on nothing but the Python standard
library and the log file itself — no network, no Hardseal service, no trust in
us. Run it in 30 years and it still answers the same question: was this record
tampered with?

    python3 scripts/verify_chain.py
    python3 scripts/verify_chain.py path/to/INTEGRITY_LOG.md
    python3 scripts/verify_chain.py --quiet      # exit code only (0 = intact)

Exit code: 0 if the chain is fully intact, 1 if any link is broken or the
file/anchor is missing. Designed to be safe to wire into CI as a gate.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

DEFAULT_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "integrity", "INTEGRITY_LOG.md",
)

HEARTBEAT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
ANCHOR_RE = re.compile(r"^# CHAIN_ANCHOR")
GUARDIAN_SEP = " | guardian_sha="


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def split_base_and_guardian(line: str) -> tuple[str, str] | None:
    """Return (line_without_guardian_sha, guardian_sha_value) or None if absent.

    The base is everything before ' | guardian_sha=' — exactly the LINE_BASE the
    workflow hashes. The guardian value is parsed from the 'guardian_sha=' field
    regardless of any trailing fields (e.g. ' | next=...').
    """
    if GUARDIAN_SEP not in line:
        return None
    base = line.split(GUARDIAN_SEP, 1)[0]
    for field in (f.strip() for f in line.split("|")):
        if field.startswith("guardian_sha="):
            return base, field[len("guardian_sha="):]
    return None


def check_chain(log_path: str) -> dict:
    """Re-derive the chain and return a structured result.

    Keys: ok (bool overall), error (str|None for fatal problems like missing
    file/anchor), intact (bool), checked, total, broken (list[(idx, why)]),
    anchor, first_ts, last_ts.
    """
    result = {
        "ok": False, "error": None, "intact": False,
        "checked": 0, "total": 0, "broken": [],
        "anchor": "", "first_ts": "", "last_ts": "",
    }

    if not os.path.isfile(log_path):
        result["error"] = f"log not found: {log_path}"
        return result

    with open(log_path, "r", encoding="utf-8") as fh:
        raw_lines = [l.rstrip("\n") for l in fh]

    anchor = next((l for l in raw_lines if ANCHOR_RE.match(l)), None)
    if anchor is None:
        result["error"] = "no '# CHAIN_ANCHOR' seed line found"
        return result

    heartbeats = [l for l in raw_lines if HEARTBEAT_RE.match(l)]
    if not heartbeats:
        result["error"] = "no heartbeat lines found"
        return result

    prev_full = anchor
    broken: list[tuple[int, str]] = []
    checked = 0
    for idx, line in enumerate(heartbeats, start=1):
        parsed = split_base_and_guardian(line)
        if parsed is None:
            broken.append((idx, "missing guardian_sha field"))
            prev_full = line
            continue
        base, claimed = parsed
        computed = sha256_hex(prev_full + base)
        checked += 1
        if computed != claimed:
            broken.append((idx, f"expected {computed[:16]}…, found {claimed[:16]}…"))
        prev_full = line

    result.update(
        ok=not broken, intact=not broken, checked=checked, total=len(heartbeats),
        broken=broken, anchor=anchor,
        first_ts=heartbeats[0].split("|", 1)[0].strip(),
        last_ts=heartbeats[-1].split("|", 1)[0].strip(),
    )
    return result


def verify(log_path: str, quiet: bool = False) -> int:
    r = check_chain(log_path)
    if r["error"]:
        print(f"verify_chain: FAIL — {r['error']}", file=sys.stderr)
        return 1

    anchor = r["anchor"]
    heartbeats_total = r["total"]
    checked = r["checked"]
    broken = r["broken"]
    intact = r["intact"]

    if not quiet:
        print(f"verify_chain: anchor   = {anchor}")
        print(f"verify_chain: span     = {r['first_ts']}  ->  {r['last_ts']}")
        print(f"verify_chain: links    = {checked} verified of {heartbeats_total} heartbeats")
        if intact:
            print(f"verify_chain: result   = INTACT — every guardian_sha re-derives. Chain unbroken.")
        else:
            print(f"verify_chain: result   = BROKEN — {len(broken)} link(s) failed:")
            for ln, why in broken[:20]:
                print(f"  - heartbeat #{ln}: {why}")
            if len(broken) > 20:
                print(f"  … and {len(broken) - 20} more")

    return 0 if intact else 1


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:]]
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]
    log_path = args[0] if args else DEFAULT_LOG
    return verify(log_path, quiet=quiet)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
