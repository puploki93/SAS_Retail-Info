#!/usr/bin/env python3
"""Build a static documentation site from Do_This_Bitch contents."""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    import markdown2  # type: ignore
except ImportError:  # pragma: no cover
    markdown2 = None

try:  # pragma: no cover - optional dependency
    import pypandoc  # type: ignore
except ImportError:
    pypandoc = None

try:  # pragma: no cover - optional dependency
    from pdf2image import convert_from_path  # type: ignore
except ImportError:
    convert_from_path = None

logger = logging.getLogger("builder")

SUPPORTED_MEDIA = {".png", ".jpg", ".jpeg", ".gif"}
SUPPORTED_DOCS = {".pdf", ".docx"}
README_NAMES = {"readme.md", "readme"}


@dataclass
class PageInfo:
    title: str
    slug: str
    source_dir: Path
    output_file: Path


def slugify(name: str) -> str:
    return "-".join(part for part in name.strip().split()) or "folder"


def convert_markdown(md_path: Path) -> str:
    logger.debug("Converting markdown: %s", md_path)
    text = md_path.read_text(encoding="utf-8")
    if pypandoc:
        try:
            return pypandoc.convert_text(text, "html", format="md")
        except Exception as exc:  # pragma: no cover
            logger.warning("pypandoc failed for %s: %s", md_path, exc)
    if markdown2:
        return markdown2.markdown(text)
    import html

    return "<pre>" + html.escape(text) + "</pre>"


def copy_asset(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def pdf_preview(pdf_src: Path, dest_dir: Path) -> Optional[Path]:
    if not convert_from_path:
        return None
    try:
        images = convert_from_path(str(pdf_src), first_page=1, last_page=1)
    except Exception as exc:  # pragma: no cover
        logger.warning("Unable to render PDF preview for %s: %s", pdf_src, exc)
        return None
    if not images:
        return None
    preview_path = dest_dir / f"{pdf_src.stem}_preview.png"
    images[0].save(preview_path, "PNG")
    return preview_path


def render_docx(docx_src: Path) -> Optional[str]:
    if not pypandoc:
        return None
    try:
        return pypandoc.convert_file(str(docx_src), "html")
    except Exception as exc:  # pragma: no cover
        logger.warning("Unable to convert DOCX %s: %s", docx_src, exc)
        return None


def build_page(page: PageInfo, assets_root: Path) -> None:
    logger.info("Building page for %s", page.source_dir)
    asset_dir = assets_root / page.slug
    asset_dir.mkdir(parents=True, exist_ok=True)

    media_blocks: List[str] = []
    doc_blocks: List[str] = []
    readme_html = ""

    for item in sorted(page.source_dir.iterdir()):
        if item.is_dir():
            continue
        if item.name.lower() in README_NAMES:
            try:
                readme_html = convert_markdown(item)
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to convert %s: %s", item, exc)
            continue

        suffix = item.suffix.lower()
        dest_path = asset_dir / item.name
        copy_asset(item, dest_path)

        if suffix in SUPPORTED_MEDIA:
            media_blocks.append(
                f'<figure><img src="assets/{page.slug}/{dest_path.name}" alt="{item.name}"><figcaption>{item.name}</figcaption></figure>'
            )
        elif suffix == ".pdf":
            preview = pdf_preview(item, asset_dir)
            preview_tag = (
                f'<img src="assets/{page.slug}/{preview.name}" alt="Preview of {item.name}">' if preview else ""
            )
            doc_blocks.append(
                f'<article class="doc-block"><h3>{item.name}</h3>{preview_tag}<p><a href="assets/{page.slug}/{dest_path.name}">Download PDF</a></p></article>'
            )
        elif suffix == ".docx":
            rendered = render_docx(dest_path)
            doc_html = rendered or f'<p><a href="assets/{page.slug}/{dest_path.name}">Download DOCX</a></p>'
            doc_blocks.append(f'<article class="doc-block"><h3>{item.name}</h3>{doc_html}</article>')
        else:
            logger.debug("Skipping unsupported file %s", item)

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{page.title}</title>
  <link rel=\"stylesheet\" href=\"style.css\">
</head>
<body>
  <header>
    <h1>{page.title}</h1>
    <nav><a href=\"index.html\">Home</a></nav>
  </header>
  <main>
    {readme_html}
    <section class=\"media-grid\">
      {''.join(media_blocks)}
    </section>
    <section class=\"doc-grid\">
      {''.join(doc_blocks)}
    </section>
  </main>
  <footer>Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</footer>
</body>
</html>"""
    page.output_file.write_text(html, encoding="utf-8")


def build_index(pages: List[PageInfo], build_dir: Path) -> None:
    logger.info("Building index page")
    buttons = "".join(
        f'<button onclick="window.location.href=\'{page.output_file.name}\'">{page.title}</button>'
        for page in pages
    )
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Documentation Hub</title>
  <link rel=\"stylesheet\" href=\"style.css\">
</head>
<body>
  <header>
    <h1>Documentation Hub</h1>
    <p>Select a collection to view its resources.</p>
  </header>
  <main class=\"button-grid\">
    {buttons}
  </main>
  <footer>Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</footer>
</body>
</html>"""
    (build_dir / "index.html").write_text(html, encoding="utf-8")


def write_css(build_dir: Path) -> None:
    css = """body {font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background:#f4f6fb; color:#1f2933;}
header {background:linear-gradient(135deg,#1e3a8a,#1d4ed8);color:#fff;padding:2rem;text-align:center;}
main {padding:2rem;}
nav a {color:#fff;text-decoration:none;}
.button-grid {display:flex;flex-wrap:wrap;gap:1rem;justify-content:center;}
.button-grid button {padding:1rem 2rem;border:none;border-radius:12px;background:#2563eb;color:#fff;font-size:1.1rem;cursor:pointer;box-shadow:0 10px 20px rgba(37,99,235,0.25);transition:transform 0.2s ease, box-shadow 0.2s ease;}
.button-grid button:hover {transform:translateY(-2px);box-shadow:0 12px 24px rgba(37,99,235,0.35);}
.media-grid, .doc-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.5rem;margin-top:2rem;}
figure {background:#fff;border-radius:12px;box-shadow:0 6px 12px rgba(15,23,42,0.1);padding:1rem;text-align:center;}
figure img {max-width:100%;border-radius:8px;}
.doc-block {background:#fff;border-radius:12px;box-shadow:0 6px 12px rgba(15,23,42,0.1);padding:1.25rem;}
footer {text-align:center;padding:1rem;color:#475569;}
"""
    (build_dir / "style.css").write_text(css, encoding="utf-8")


def run_git_commands(root: Path) -> None:
    cmds = [
        ["git", "add", "build", "scripts/build_static_doc_site.py"],
        ["git", "commit", "-m", "Auto-built static doc site"],
        ["git", "push", "origin", "main"],
    ]
    for cmd in cmds:
        logger.info("Running git command: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, cwd=root, check=True)
        except subprocess.CalledProcessError as exc:
            logger.error("Git command failed (%s): %s", " ".join(cmd), exc)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="Do_This_Bitch",
        help="Relative path to source directory (default: Do_This_Bitch)",
    )
    parser.add_argument(
        "--build",
        default="build",
        help="Relative path for build output (default: build)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    root = Path(__file__).resolve().parents[1]
    source_dir = root / args.source
    build_dir = root / args.build
    assets_dir = build_dir / "assets"

    if not source_dir.exists():
        logger.error("Source directory not found: %s", source_dir)
        sys.exit(1)

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)

    pages: List[PageInfo] = []

    for subdir in sorted(source_dir.iterdir()):
        if not subdir.is_dir():
            continue
        slug = slugify(subdir.name)
        page = PageInfo(
            title=subdir.name.strip() or subdir.name,
            slug=slug,
            source_dir=subdir,
            output_file=build_dir / f"{slug}.html",
        )
        try:
            build_page(page, assets_dir)
            pages.append(page)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to build page for %s: %s", subdir, exc)

    build_index(pages, build_dir)
    write_css(build_dir)

    logger.info("Build complete. Output at %s", build_dir)

    try:
        run_git_commands(root)
    except Exception:
        logger.warning("Git operations failed. Please check the repository state and try again.")


if __name__ == "__main__":
    main()
