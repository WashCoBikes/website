#!/usr/bin/env python3
"""Check Markdown image descriptions without modifying content.

Checks inline and reference-style images in src/content. The browser
accessibility audit covers rendered HTML and component images.
"""

import argparse
from pathlib import Path
import re
import sys

CONTENT = Path(__file__).resolve().parent.parent / "src" / "content"
EMPTY_ALT = re.compile(r"!\[\s*\]\s*(?:\(|\[)")


def check(content: Path) -> int:
    paths = sorted(content.rglob("*.md"))
    if not paths:
        print(f"No Markdown files found in {content}", file=sys.stderr)
        return 1
    missing = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in EMPTY_ALT.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            missing.append(f"{path.relative_to(content)}:{line}: empty image alt text")
    if missing:
        print("\n".join(missing), file=sys.stderr)
        return 1
    print("All Markdown images have alt text.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=CONTENT)
    sys.exit(check(parser.parse_args().content))
