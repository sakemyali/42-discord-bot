#!/usr/bin/env python3
"""Convert Q&A/ HTML and PDF files to chunkable markdown in corpus/intra/.

- HTML: trafilatura article extraction with markdown output, falls back to
  BeautifulSoup body extraction with markdownify if trafilatura returns nothing.
- PDF: pdftotext (must be on PATH).
- Other files (images, etc.) are skipped with a notice.

Filenames are sanitized for filesystem safety but preserve Japanese characters.
The original page title is written as the H1 of each markdown file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify as md

SRC = Path("Q&A")
DST = Path("corpus/intra")

EMOJI_RE = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "]+",
    flags=re.UNICODE,
)


def sanitize_filename(name: str) -> str:
    name = name.removesuffix(".html").removesuffix(".pdf")
    name = name.replace(" - Google ドライブ", "")
    name = name.replace(".docx", "")
    name = name.replace(".pdf", "")
    name = EMOJI_RE.sub("", name)
    name = name.replace("/", "-").replace(":", "-").replace("\\", "-")
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip("_- ")
    if not name:
        name = "untitled"
    return name + ".md"


def extract_title(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for sel in ["h1", "title"]:
        tag = soup.find(sel)
        if tag and tag.get_text(strip=True):
            return tag.get_text(strip=True)
    return fallback


def html_to_md_trafilatura(html: str) -> str | None:
    out = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_links=False,
        favor_recall=True,
    )
    if out and out.strip():
        return out.strip()
    return None


def html_to_md_fallback(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "noscript",
            "iframe",
        ]
    ):
        tag.decompose()
    for cls in [
        "main-navbar",
        "page-sidebar",
        "notifications-container",
        "left-sidebar-fix",
        "user-actions",
        "main-navbar-left",
        "main-navbar-user-nav",
    ]:
        for tag in soup.find_all(class_=cls):
            tag.decompose()
    body = soup.find("article") or soup.find("main") or soup.body or soup
    out = md(str(body), heading_style="ATX", strip=["a", "img"])
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def write_md(dst: Path, title: str, body: str, source: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    body = collapse_blank_lines(body)
    body = unicodedata.normalize("NFC", body)
    front = f"# {title}\n\n_Source: {source}_\n\n"
    dst.write_text(front + body + "\n", encoding="utf-8")


def convert_html(path: Path) -> tuple[str, int]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    title = extract_title(html, fallback=path.stem)
    body = html_to_md_trafilatura(html)
    used = "trafilatura"
    if not body or len(body) < 80:
        body = html_to_md_fallback(html)
        used = "fallback"
    out_name = sanitize_filename(path.name)
    write_md(DST / out_name, title=title, body=body, source=path.name)
    return used, len(body)


def convert_pdf(path: Path) -> tuple[str, int]:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not on PATH; install poppler")
    proc = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    body = collapse_blank_lines(proc.stdout)
    title = path.stem
    out_name = sanitize_filename(path.name)
    write_md(DST / out_name, title=title, body=body, source=path.name)
    return "pdftotext", len(body)


def main() -> int:
    if not SRC.exists():
        print(f"source folder not found: {SRC}", file=sys.stderr)
        return 1
    DST.mkdir(parents=True, exist_ok=True)
    n_html = n_pdf = n_skip = 0
    short = []
    for path in sorted(SRC.iterdir()):
        if path.is_dir():
            continue
        suf = path.suffix.lower()
        try:
            if suf in {".html", ".htm"}:
                used, size = convert_html(path)
                n_html += 1
                if size < 300:
                    short.append((path.name, size, used))
                print(f"[html/{used:>11}] {path.name} -> {size} chars")
            elif suf == ".pdf":
                used, size = convert_pdf(path)
                n_pdf += 1
                print(f"[pdf /{used:>11}] {path.name} -> {size} chars")
            else:
                n_skip += 1
                print(f"[skip          ] {path.name}")
        except Exception as e:
            print(f"[error         ] {path.name}: {e}", file=sys.stderr)
    print()
    print(f"converted: {n_html} HTML, {n_pdf} PDF; skipped {n_skip}")
    if short:
        print("\nshort outputs (<300 chars) — may need manual review:")
        for name, size, used in short:
            print(f"  {size:>5} chars [{used}] {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
