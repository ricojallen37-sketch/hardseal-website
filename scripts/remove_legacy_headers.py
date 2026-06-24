#!/usr/bin/env python3
"""Remove duplicate legacy <header> blocks when site-header is present."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER_RE = re.compile(r"<header(?![^>]*class=\"site-header\")[^>]*>.*?</header>\s*", re.DOTALL)


def main() -> None:
    for html in ROOT.rglob("*.html"):
        if html.as_posix().startswith(str(ROOT / "proof")):
            continue
        text = html.read_text(encoding="utf-8")
        if 'class="site-header"' not in text:
            continue
        new = HEADER_RE.sub("", text)
        if new != text:
            html.write_text(new, encoding="utf-8")
            print(f"cleaned {html.relative_to(ROOT)}")


if __name__ == "__main__":
    main()