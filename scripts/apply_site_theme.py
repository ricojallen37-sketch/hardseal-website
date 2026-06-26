#!/usr/bin/env python3
"""Inject unified Hardseal theme + navigation into public HTML pages."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PREFIXES = ("proof/",)
SKIP_FILES = set()

THEME_LINKS = """<link rel="stylesheet" href="/assets/site-nav.css">
<link rel="stylesheet" href="/assets/theme-spacex.css">"""

NAV_SNIPPET = """<header class="site-header">
  <div class="site-header-inner">
    <a href="/" class="site-brand" aria-label="Hardseal home">
      <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <rect width="32" height="32" rx="6" fill="#000"/>
        <path d="M8 10 L16 6 L24 10 L24 18 C24 22 20 25 16 26 C12 25 8 22 8 18 Z" stroke="#ffffff" stroke-width="1.75" stroke-linejoin="round"/>
        <path d="M12 16 L15 19 L20 13" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      HARDSEAL
    </a>
    <button class="site-menu-btn" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="site-nav">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
    <nav class="site-nav" id="site-nav" aria-label="Primary">
      <a href="/verify.html">Verifier</a>
      <a href="/trophy-case.html">Proof</a>
      <a href="/client-experience.html">Experience</a>
      <a href="/pilot.html">Review</a>
      <a href="/resources.html">Resources</a>
      <a href="/pilot.html" class="site-nav-cta">Start</a>
    </nav>
  </div>
</header>
"""

NAV_JS = '<script src="/assets/site-nav.js" defer></script>'

GREEN_ROOT = re.compile(
    r"--green:\s*#00[Ff]{2}88[^;]*;|--green:\s*#00ff88[^;]*;",
    re.MULTILINE,
)


def should_process(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel in SKIP_FILES:
        return False
    return not any(rel.startswith(p) for p in SKIP_PREFIXES)


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    if "theme-spacex.css" not in text and "</style>" in text:
        text = text.replace("</style>", f"</style>\n{THEME_LINKS}", 1)

    if 'class="site-header"' not in text and "<body" in text:
        text = re.sub(r"(<body[^>]*>)", r"\1\n" + NAV_SNIPPET, text, count=1)

    if "site-nav.js" not in text:
        if "</body>" in text:
            text = text.replace("</body>", f"{NAV_JS}\n</body>", 1)

    text = GREEN_ROOT.sub("--green:var(--accent);", text)
    text = text.replace("#00FF88", "#ffffff").replace("#00ff88", "#ffffff")
    text = text.replace("#2F80FF", "#ffffff").replace("#2f80ff", "#ffffff")
    text = text.replace("#3b8cff", "#ffffff").replace("#1267d8", "#e8e8e8")

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    for html in sorted(ROOT.rglob("*.html")):
        if should_process(html):
            if patch_file(html):
                changed.append(html.relative_to(ROOT))
    print(f"Patched {len(changed)} file(s):")
    for p in changed:
        print(f"  - {p}")


if __name__ == "__main__":
    main()