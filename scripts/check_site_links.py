"""Check internal links and anchors in a built Jekyll site.

Usage: python scripts/check_site_links.py <site_dir> [--baseurl /revitpy]
Exits 1 and lists broken links if any internal href or #anchor is missing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("site_dir", type=Path)
    parser.add_argument("--baseurl", default="/revitpy")
    args = parser.parse_args()

    site: Path = args.site_dir
    prefix = args.baseurl.rstrip("/") + "/"
    pages = {p: p.read_text(encoding="utf-8") for p in site.rglob("*.html")}
    ids = {p: set(re.findall(r'id="([^"]+)"', text)) for p, text in pages.items()}

    broken: list[str] = []
    for page, text in pages.items():
        for href in re.findall(r'href="([^"?]+)"', text):
            if not href.startswith(prefix):
                continue
            path, _, anchor = href[len(prefix) :].partition("#")
            target = site / path
            if path == "" or path.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                broken.append(f"{page.relative_to(site)} -> {href}")
            elif anchor and target.suffix == ".html" and anchor not in ids[target]:
                broken.append(f"{page.relative_to(site)} -> {href} (missing anchor)")

    for line in broken:
        print(line)
    print(f"checked {len(pages)} pages, {len(broken)} broken links")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
