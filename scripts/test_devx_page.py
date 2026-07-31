"""Truth-boundary tests for the DevX evaluator page."""

from __future__ import annotations

import unittest
from pathlib import Path


PAGE = Path(__file__).resolve().parent.parent / "devx.html"


class DevXPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_required_positioning_is_present(self) -> None:
        for phrase in (
            "DevX Autonomy",
            "Sustainment Solutions",
            "TRL 4",
            "SUPPORTED",
            "CONTRADICTED",
            "UNAVAILABLE",
            "OUT OF SCOPE",
            "No federal past performance",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_claim_boundary_is_present(self) -> None:
        for phrase in (
            "does not establish physical",
            "independent IV&amp;V",
            "root-cause",
            "Current scope excludes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_page_has_no_external_runtime_dependency(self) -> None:
        self.assertNotIn("<script src=", self.text)
        self.assertNotIn("<link rel=\"stylesheet\"", self.text)

    def test_canonical_is_exact(self) -> None:
        self.assertIn('href="https://hardseal.ai/devx.html"', self.text)


if __name__ == "__main__":
    unittest.main()
