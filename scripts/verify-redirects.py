#!/usr/bin/env python3
"""Verify every URL on the live site resolves in the new site.

Checks each <loc> in the live sitemap against the built output in dist/ and
the rules in public/_redirects. A URL passes if it is either a built route or
matched by a redirect rule.

This is the guard on the IA consolidation: the flattened sitemap is only safe
because every retired URL still lands somewhere sensible. Run it after changing
routes or redirects.

Usage (from repo root):

    mise run verify

    python scripts/verify-redirects.py [--sitemap URL_OR_PATH]

Requires a build first (reads dist/). Standard library only.

Exit status is 0 when every URL resolves, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_SITEMAP = "https://washcobikes.org/sitemap.xml"
ROOT = Path(__file__).resolve().parent.parent


def load_sitemap(source: str) -> list[str]:
    """Return the sitemap's <loc> values as root-relative paths."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            xml = response.read().decode("utf-8", "replace")
    else:
        xml = Path(source).read_text(encoding="utf-8", errors="replace")

    paths = set()
    for loc in re.findall(r"<loc>(.*?)</loc>", xml, re.DOTALL):
        path = re.sub(r"^https?://[^/]+", "", loc.strip()).rstrip("/")
        paths.add(path or "/")
    return sorted(paths)


def load_routes(dist: Path) -> set[str]:
    """Return the routes present in the built output."""
    routes = set()
    for index in dist.rglob("index.html"):
        relative = index.parent.relative_to(dist).as_posix()
        routes.add("/" if relative == "." else "/" + relative)
    return routes


def load_rules(redirects: Path) -> list[tuple[str, str]]:
    """Return (source, target) pairs from a Netlify _redirects file."""
    rules = []
    for line in redirects.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            rules.append((fields[0].rstrip("/") or "/", fields[1]))
    return rules


def resolve(path: str, routes: set[str], rules: list[tuple[str, str]]) -> str | None:
    """Return how this path resolves, or None if nothing handles it."""
    if path in routes:
        return "route"
    for source, target in rules:
        if source == path:
            return f"redirect -> {target}"
        if source.endswith("/*") and path.startswith(source[:-2]):
            return f"splat -> {target}"
        if source.startswith("/*.") and path.endswith(source[2:]):
            return f"splat -> {target}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sitemap",
        default=DEFAULT_SITEMAP,
        help=f"sitemap URL or local path (default: {DEFAULT_SITEMAP})",
    )
    args = parser.parse_args()

    dist = ROOT / "dist"
    if not dist.is_dir():
        print("dist/ not found — run `mise run build` first.", file=sys.stderr)
        return 1

    redirects = ROOT / "public" / "_redirects"
    if not redirects.is_file():
        print("public/_redirects not found.", file=sys.stderr)
        return 1

    paths = load_sitemap(args.sitemap)
    routes = load_routes(dist)
    rules = load_rules(redirects)

    unresolved = [path for path in paths if resolve(path, routes, rules) is None]

    print(
        f"{len(paths)} sitemap URLs "
        f"vs {len(routes)} built routes + {len(rules)} redirect rules"
    )

    if unresolved:
        print(f"\nUNRESOLVED ({len(unresolved)}):", file=sys.stderr)
        for path in unresolved:
            print(f"  {path}", file=sys.stderr)
        return 1

    print("All URLs resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
