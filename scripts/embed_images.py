#!/usr/bin/env python3
"""Embed local relative <img src> files as data URIs without changing the source HTML."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


SRC_RE = re.compile(r"(?P<prefix>\bsrc\s*=\s*)(?P<quote>['\"])(?P<src>[^'\"]+)(?P=quote)", re.I)


def embed_html(html_path: Path, output_path: Path) -> tuple[int, int]:
    html = html_path.read_text(encoding="utf-8")
    base_dir = html_path.parent
    embedded = 0
    skipped = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal embedded, skipped
        src = match.group("src")
        parsed = urlparse(src)
        if parsed.scheme or src.startswith("//") or src.startswith("#"):
            skipped += 1
            return match.group(0)
        image_path = (base_dir / unquote(src)).resolve()
        if not image_path.is_file():
            skipped += 1
            return match.group(0)
        mime, _ = mimetypes.guess_type(image_path.name)
        mime = mime or "application/octet-stream"
        payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
        embedded += 1
        return f'{match.group("prefix")}{match.group("quote")}data:{mime};base64,{payload}{match.group("quote")}'

    result = SRC_RE.sub(replace, html)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    return embedded, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed local HTML images as data URIs.")
    parser.add_argument("--html", required=True, type=Path, help="Input HTML file")
    parser.add_argument("--output", required=True, type=Path, help="Output HTML file")
    args = parser.parse_args()

    if not args.html.is_file():
        parser.error(f"HTML file not found: {args.html}")
    embedded, skipped = embed_html(args.html, args.output)
    print(f"embedded={embedded} skipped={skipped} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
