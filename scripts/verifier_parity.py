#!/usr/bin/env python3
"""JS <-> Python verifier parity harness.

The whole "verify it yourself in your browser" claim rests on the browser
verifier (assets/hardseal-verifier.js) producing the SAME verdict and the
SAME recomputed SHA-256 chain root as the canonical Python verifiers
(downloads/verify_cmmc_packet_qa.py and downloads/verify_standalone.py).

If the two ever drift, the public page could say PASS while the air-gapped
Python verifier says FAIL -- silently breaking "independently verifiable,"
which is the moat. This harness fails the build the moment they disagree.

For every public receipt it checks, on both the clean packet and a tampered
copy, it asserts:
    (passed, recomputed_chain_root)  JS  ==  Python

Requires `node`. Standard library only on the Python side. Run:
    python3 scripts/verifier_parity.py

Exit 0 = JS and Python agree on every case; non-zero = a divergence (or a
missing receipt / missing node), which must block release.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "downloads"))

import verify_cmmc_packet_qa as cmmc  # noqa: E402
import verify_standalone as edge  # noqa: E402

RUNNER = ROOT / "scripts" / "verifier_parity_runner.js"

# Receipts that ship to the public and are loadable by /v/.
RECEIPTS = [
    "cmmc-packet-qa-receipt5.json",
    "sample-packet-receipt1.json",
    "cmmc-audit-log-receipt2.json",
    "poam-evidence-receipt3.json",
    "ssp-change-history-receipt4.json",
]

# Text-level mutations that land inside a HASHED section, so both verifiers
# must recompute the same (now-mismatching) root and both must FAIL. Only the
# two receipts whose section content is asserted here get a tamper case; the
# rest are clean-parity only (logged honestly as such).
TAMPERS = {
    "cmmc-packet-qa-receipt5.json": ("partially_supported", "fully_supported___"),
    "sample-packet-receipt1.json": ("synthetic input", "xynthetic input"),
}


def py_eval(text: str):
    """Return (passed, recomputed_root_or_None, format) from Python."""
    d = json.loads(text)
    if d.get("receipt_type") == cmmc.RECEIPT_TYPE:
        r = cmmc.verify_receipt(d)
        return bool(r.passed), (r.chain_root or None), "cmmc"
    passed = bool(edge.verify_packet(d).passed)
    try:
        root, _ = edge.compute_chain_root(
            d["packet_type"], d["schema_version"], d["operational_class"],
            d["session_id"], d["created_utc"], d["offline_mode"],
            {k: d[k] for k in edge.SECTION_ORDER},
        )
    except Exception:
        root = None
    return passed, root, "edge"


def js_eval(path: Path):
    """Return (passed, recomputed_root_or_None, format) from the JS verifier."""
    proc = subprocess.run(
        ["node", str(RUNNER), str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"node runner failed: {proc.stderr.strip()}")
    j = json.loads(proc.stdout)
    return bool(j["passed"]), (j.get("root") or None), j.get("format")


def check_node() -> None:
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: `node` is required for verifier parity but is unavailable: {exc}")
        sys.exit(2)


def run_case(name: str, text: str, scratch: Path, expect_pass: bool):
    """Compare JS vs Python for one packet text. Returns (ok, detail)."""
    path = scratch / name
    path.write_text(text, encoding="utf-8")
    py = py_eval(text)
    js = js_eval(path)
    agree = (py[0] == js[0]) and (py[1] == js[1])
    verdict_ok = (py[0] == expect_pass)
    detail = (
        f"py=({py[0]},{(py[1] or '')[:12]}) "
        f"js=({js[0]},{(js[1] or '')[:12]}) fmt={py[2]}/{js[2]}"
    )
    return agree and verdict_ok, agree, verdict_ok, detail


def main() -> int:
    check_node()
    if not RUNNER.exists():
        print(f"FAIL: missing JS runner {RUNNER}")
        return 2

    import tempfile
    failures = 0
    checks = 0
    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td)
        for name in RECEIPTS:
            src = ROOT / name
            if not src.exists():
                print(f"  FAIL: [parity] receipt missing: {name}")
                failures += 1
                continue
            clean = src.read_text(encoding="utf-8")

            ok, agree, vok, detail = run_case(name, clean, scratch, expect_pass=True)
            checks += 1
            if ok:
                print(f"  PASS: [parity] {name} clean -> JS==Python, both PASS | {detail}")
            else:
                failures += 1
                why = "JS/Python DIVERGE" if not agree else "did not PASS as expected"
                print(f"  FAIL: [parity] {name} clean -> {why} | {detail}")

            if name in TAMPERS:
                find, repl = TAMPERS[name]
                if find not in clean:
                    print(f"  FAIL: [parity] {name} tamper anchor '{find}' not found")
                    failures += 1
                    continue
                tampered = clean.replace(find, repl, 1)
                ok, agree, vok, detail = run_case(
                    "tampered-" + name, tampered, scratch, expect_pass=False
                )
                checks += 1
                if ok:
                    print(f"  PASS: [parity] {name} tampered -> JS==Python, both FAIL | {detail}")
                else:
                    failures += 1
                    why = "JS/Python DIVERGE" if not agree else "did not FAIL as expected"
                    print(f"  FAIL: [parity] {name} tampered -> {why} | {detail}")

    print()
    if failures:
        print(f"verifier parity: FAIL ({failures} divergence(s) across {checks} checks)")
        return 1
    print(f"verifier parity: PASS ({checks} checks, JS verifier is byte-conformant with Python)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
