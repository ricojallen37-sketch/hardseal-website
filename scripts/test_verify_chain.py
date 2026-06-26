#!/usr/bin/env python3
"""
test_verify_chain.py — lock in the integrity-chain verifier's correctness.

Doctrine: if the system can fail the same way twice, it has not learned. The
trust page's entire claim rests on verify_chain.py correctly (a) accepting an
untampered chain and (b) detecting ANY alteration. These tests prove both,
against a synthetic log built with the exact same guardian_sha formula the
GitHub Actions heartbeat uses, plus the real committed log if present.

Run:  python3 scripts/test_verify_chain.py
Pure standard library. No network.
"""

import hashlib
import os
import tempfile
import unittest

import verify_chain as vc

ANCHOR = "# CHAIN_ANCHOR seed=hardseal-edge-integrity-log-v1"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def make_line(prev_full: str, ts: str, result: str = "PASS") -> str:
    """Build a heartbeat line exactly as the workflow does."""
    base = (
        f"{ts} | bundle_sha=deadbeef | bundle_bytes=1000 | "
        f"packets=12/12 | result={result} | verifier_sha=cafef00d"
    )
    guardian = sha(prev_full + base)
    return f"{base} | guardian_sha={guardian} | next={ts}"


def build_log(n: int) -> list[str]:
    lines = [ANCHOR]
    prev = ANCHOR
    for i in range(n):
        ts = f"2026-05-{(i % 28) + 1:02d}T00:00:00Z"
        line = make_line(prev, ts)
        lines.append(line)
        prev = line
    return lines


def write_log(lines) -> str:
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("# header\n\n" + "\n".join(lines) + "\n")
    return path


class TestVerifyChain(unittest.TestCase):
    def test_intact_chain_passes(self):
        path = write_log(build_log(10))
        try:
            r = vc.check_chain(path)
            self.assertIsNone(r["error"])
            self.assertTrue(r["intact"])
            self.assertEqual(r["checked"], 10)
            self.assertEqual(r["broken"], [])
        finally:
            os.remove(path)

    def test_tamper_breaks_line_and_successor(self):
        lines = build_log(10)
        # Alter a field in the 5th heartbeat (index 5: anchor is index 0).
        target = 5
        lines[target] = lines[target].replace("bundle_bytes=1000", "bundle_bytes=9999")
        path = write_log(lines)
        try:
            r = vc.check_chain(path)
            self.assertFalse(r["intact"])
            broken_idx = {i for i, _ in r["broken"]}
            # Heartbeat #5 (its base changed) and #6 (its prev changed) must break.
            self.assertIn(5, broken_idx)
            self.assertIn(6, broken_idx)
        finally:
            os.remove(path)

    def test_guardian_edit_is_detected(self):
        lines = build_log(6)
        # Flip one hex char of a guardian_sha.
        t = 3
        line = lines[t]
        g = line.split("guardian_sha=")[1].split(" |")[0]
        flipped = ("1" if g[0] != "1" else "2") + g[1:]
        lines[t] = line.replace("guardian_sha=" + g, "guardian_sha=" + flipped)
        path = write_log(lines)
        try:
            r = vc.check_chain(path)
            self.assertFalse(r["intact"])
            self.assertIn(3, {i for i, _ in r["broken"]})
        finally:
            os.remove(path)

    def test_deleted_line_is_detected(self):
        lines = build_log(8)
        del lines[4]  # remove a heartbeat; successor's prev no longer matches
        path = write_log(lines)
        try:
            r = vc.check_chain(path)
            self.assertFalse(r["intact"])
        finally:
            os.remove(path)

    def test_missing_anchor_is_fatal(self):
        lines = [l for l in build_log(3) if not l.startswith("# CHAIN_ANCHOR")]
        path = write_log(lines)
        try:
            r = vc.check_chain(path)
            self.assertIsNotNone(r["error"])
            self.assertFalse(r["ok"])
        finally:
            os.remove(path)

    def test_real_committed_log_is_intact(self):
        """If the real log is present, it must verify clean. Guards against a
        verifier change that silently stops matching production receipts."""
        if not os.path.isfile(vc.DEFAULT_LOG):
            self.skipTest("real INTEGRITY_LOG.md not present")
        r = vc.check_chain(vc.DEFAULT_LOG)
        self.assertIsNone(r["error"])
        self.assertTrue(r["intact"], f"real chain broken: {r['broken'][:5]}")
        self.assertGreater(r["checked"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
