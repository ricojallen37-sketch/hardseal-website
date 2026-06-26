#!/usr/bin/env python3
"""post_card.py — turn a sealed Hardseal Edge packet into a LinkedIn-ready post.

Content mint on top of the evidence mint. Give it a packet.json; it:

  1. Recomputes the SHA-256 chain root independently (same algorithm as the
     standalone verifier) and checks it against the stored root.
  2. Runs the shipped standalone verifier and confirms `result: PASS`.
  3. ONLY THEN prints a paste-ready LinkedIn "receipt" card whose every
     number comes from the packet bytes — never from memory.

If the root does not recompute or the verifier does not PASS, it refuses to
emit a card and exits non-zero. The generator holds the same line the product
does: no claim without the bytes.

Stdlib-only. No pip. No network.

Usage:
    python3 scripts/post_card.py <path-to-packet.json> [--verifier PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

GENESIS_LABEL = "HARDSEAL_EDGE_GENESIS_v1"
SECTION_ORDER = ("device", "model", "benchmark", "sensors", "limitations")
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VERIFIER = REPO_ROOT / "downloads" / "verify_standalone.py"

# Display names for known platforms; falls back to a title-cased slug.
PLATFORM_DISPLAY = {
    "jetson_orin_nano_super": "Jetson Orin Nano Super",
}


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def compute_chain_root(p: dict) -> str:
    parts = [
        GENESIS_LABEL,
        p["packet_type"],
        p["schema_version"],
        p["operational_class"],
        p["session_id"],
        p["created_utc"],
        str(p["offline_mode"]).lower(),
    ]
    prev = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    for name in SECTION_ORDER:
        prev = hashlib.sha256(canonical_json(p[name]) + prev.encode("utf-8")).hexdigest()
    return prev


def run_verifier(verifier: Path, packet_path: Path) -> bool:
    try:
        out = subprocess.run(
            [sys.executable, str(verifier), str(packet_path)],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: could not run verifier {verifier}: {exc}", file=sys.stderr)
        return False
    return out.returncode == 0 and "result: PASS" in out.stdout


def fmt_card(p: dict, root: str) -> str:
    dev, mdl, ben = p["device"], p["model"], p["benchmark"]
    iters = ben.get("recorded_iterations")
    hours = ben["wall_seconds"] / 3600.0
    clocks = ", clocks pinned" if dev.get("clocks_pinned") else ""
    scope = (p.get("limitations") or ["scope declared in packet"])[0]
    session = p["session_id"]

    platform = PLATFORM_DISPLAY.get(dev["platform"], dev["platform"].replace("_", " ").title())
    headline = f"{iters:,} inferences. {hours:.2f} h." if iters else f"{hours:.2f} h sustained."
    return f"""{headline}
One {platform} @ {dev.get('power_mode', 'n/a')}{clocks}.

{mdl['name']} {mdl['precision'].upper()} on {mdl['runtime']} {mdl.get('runtime_version', '')}:
mean {ben['mean_ms']:.2f} ms, p99 {ben['p99_ms']:.2f} ms, ~{ben['throughput_fps']:.0f} FPS.

Sealed in one tamper-evident packet. Declared scope, stated inside the packet itself: {scope}.

Don't trust the number — recompute the root yourself:
  python3 verify_standalone.py {session}/packet.json
  # expect: result: PASS, and this exact chain root:
  {root}

#EdgeAI #VerifiableAI #ReceiptsNotClaims #Jetson"""


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Mint a LinkedIn receipt card from a sealed packet.")
    ap.add_argument("packet", help="path to packet.json")
    ap.add_argument("--verifier", default=str(DEFAULT_VERIFIER), help="path to verify_standalone.py")
    args = ap.parse_args(argv)

    packet_path = Path(args.packet)
    try:
        p = json.loads(packet_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not load {packet_path}: {exc}", file=sys.stderr)
        return 2

    # Gate 1: recompute the chain root independently.
    try:
        recomputed = compute_chain_root(p)
    except (KeyError, TypeError) as exc:
        print(f"ERROR: packet missing fields needed to recompute root: {exc}", file=sys.stderr)
        return 2
    stored = (p.get("integrity") or {}).get("hash_chain_root")
    if recomputed != stored:
        print("REFUSING TO MINT: recomputed chain root does not match stored root.", file=sys.stderr)
        print(f"  recomputed: {recomputed}\n  stored:     {stored}", file=sys.stderr)
        return 1

    # Gate 2: the shipped verifier must PASS.
    if not run_verifier(Path(args.verifier), packet_path):
        print("REFUSING TO MINT: standalone verifier did not return result: PASS.", file=sys.stderr)
        return 1

    print(f"[verified] chain root recomputed and matches; standalone verifier: PASS\n", file=sys.stderr)
    print(fmt_card(p, recomputed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
