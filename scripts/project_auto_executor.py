#!/usr/bin/env python3
"""
Project Auto-Executor
---------------------

Traverse a repository, discover README files, execute documented commands, and
perform visual regression checks against co-located mockups.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Optional imports for visual diffing.
try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:  # pragma: no cover - Pillow not installed
    Image = ImageChops = ImageStat = None  # type: ignore


DESTRUCTIVE_PATTERNS = [
    r"\brm\b",
    r"\bmkfs\b",
    r"\bdd\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\binit\s+0\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
    r"\bsudo\b",
]

SHELL_META_CHARS = {"|", "&", ";", ">", "<", "*", "$(", "`", "||", "&&"}
README_PATTERN = re.compile(r"^readme(?:\..*)?$", re.IGNORECASE)
INSTRUCTION_LINE_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOX_DRAWING_CHARS = {"│", "├", "└", "─", "┌", "┐", "┘", "┴", "┬", "┼", "╰", "╯", "╭", "╮"}
NETWORK_COMMAND_PATTERNS = [
    re.compile(r"^\s*git\s+clone\s+", re.IGNORECASE),
    re.compile(r"^\s*git\s+push\s+", re.IGNORECASE),
    re.compile(r"^\s*git\s+pull\s+", re.IGNORECASE),
]


def contains_box_char(text: str) -> bool:
    return any(ch in text for ch in BOX_DRAWING_CHARS)


def looks_like_command(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if contains_box_char(stripped):
        return False
    if stripped in {".", ".."}:
        return False
    if stripped.startswith("#"):
        return False
    first_token = stripped.split()[0]
    if first_token.startswith("--"):
        return False
    if first_token in {"ls", "cd"} and stripped == first_token:
        return True
    if re.match(r"^[\w./$-]", first_token):
        return True
    return False


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default="/home/sasretail/SASRetail_info",
        help="Repository root to scan (defaults to /home/sasretail/SASRetail_info).",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Custom output path for the HTML report. Defaults to <root>/logs/validation_report.html.",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Permit commands that match destructive heuristics.",
    )
    parser.add_argument(
        "--skip-visual",
        action="store_true",
        help="Skip screenshot and mockup comparisons.",
    )
    parser.add_argument(
        "--visual-tolerance",
        type=float,
        default=0.005,
        help="Allowed normalized pixel difference before flagging mismatch (default: 0.005).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-command timeout in seconds (default: 600).",
    )
    return parser.parse_args(argv)


def find_readme_files(root: Path) -> List[Path]:
    readmes: List[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and README_PATTERN.match(path.name):
            readmes.append(path)
    return sorted(readmes)


def classify_command(command: str, root: Path, allow_destructive: bool) -> Tuple[bool, str]:
    lowered = command.strip().lower()

    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, lowered):
            if allow_destructive:
                return True, ""
            return False, "Skipped destructive command (requires --allow-destructive)."

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = []

    for token in tokens:
        if token.startswith("/"):
            resolved = Path(token).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                return False, f"Command references path outside root: {token}"

    return True, ""


def needs_shell(command: str) -> bool:
    return any(meta in command for meta in SHELL_META_CHARS)


def instruction_entry(text: str, command: Optional[str], context: Optional[str]) -> Dict[str, object]:
    return {
        "text": text.strip(),
        "command": command.strip() if command else None,
        "context": context,
        "status": "pending" if command else "info",
        "details": "",
        "stdout": "",
        "stderr": "",
    }


def extract_instructions(readme_path: Path) -> List[Dict[str, object]]:
    try:
        raw = readme_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = readme_path.read_text(encoding="latin-1")

    instructions: List[Dict[str, object]] = []
    lines = raw.splitlines()

    in_code_block = False
    code_buffer: List[str] = []
    code_language: Optional[str] = None
    last_instruction_text: Optional[str] = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_language = stripped[3:].strip().lower()
                code_buffer = []
            else:
                if code_language in {"bash", "sh", "shell", ""}:
                    commands: List[str] = []
                    current = ""
                    for raw_line in code_buffer:
                        cmd_line = raw_line.strip()
                        if not cmd_line:
                            if current:
                                commands.append(current.strip())
                                current = ""
                            continue
                        if contains_box_char(cmd_line) or cmd_line.startswith("#"):
                            continue
                        trailing_backslash = cmd_line.endswith("\\")
                        if trailing_backslash:
                            cmd_line = cmd_line[:-1].rstrip()
                        current += cmd_line + (" " if trailing_backslash else "")
                        if not trailing_backslash:
                            commands.append(current.strip())
                            current = ""
                    if current.strip():
                        commands.append(current.strip())

                    for cmd in commands:
                        if not looks_like_command(cmd):
                            continue
                        context = last_instruction_text
                        text = f"{context} :: {cmd}" if context else cmd
                        instructions.append(instruction_entry(text, cmd, context))
                code_buffer = []
                in_code_block = False
                code_language = None
            continue

        if in_code_block:
            code_buffer.append(line.rstrip())
            continue

        bullet_match = INSTRUCTION_LINE_RE.match(line)
        if bullet_match:
            content = bullet_match.group(1).strip()
            instructions.append(instruction_entry(content, None, None))
            last_instruction_text = content

            inline_matches = INLINE_CODE_RE.findall(content)
            for snippet in inline_matches:
                snippet_clean = snippet.strip()
                if " " in snippet_clean and looks_like_command(snippet_clean):
                    text = f"{content} :: {snippet_clean}"
                    instructions.append(instruction_entry(text, snippet_clean, content))
            continue

        inline_matches = INLINE_CODE_RE.findall(line)
        for snippet in inline_matches:
            snippet_clean = snippet.strip()
            if " " in snippet_clean and looks_like_command(snippet_clean):
                text = snippet_clean
                instructions.append(instruction_entry(text, snippet_clean, last_instruction_text))

    return instructions


def run_command(command: str, cwd: Path, timeout: int, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
    if needs_shell(command):
        args = ["bash", "-lc", command]
    else:
        try:
            args = shlex.split(command)
        except ValueError as exc:
            raise RuntimeError(f"Unable to parse command '{command}': {exc}") from exc

    proc = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


class VisualComparator:
    def __init__(self, assets_dir: Path, tolerance: float):
        self.assets_dir = assets_dir
        self.tolerance = max(tolerance, 0.0)
        self._playwright = None
        self._browser = None
        self._engine: Optional[str] = None
        self._error: Optional[str] = None

        if Image is None:
            self._error = "Pillow is not installed; cannot perform visual diff."
            return

        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            self._error = "playwright is not installed; run `pip install playwright` and `playwright install`."
            return

        try:
            self._playwright = sync_playwright().start()
            launch_errors: List[str] = []
            for engine in ("chromium", "webkit", "firefox"):
                try:
                    browser_type = getattr(self._playwright, engine)
                    self._browser = browser_type.launch(headless=True)
                    self._engine = engine
                    break
                except Exception as exc:  # pragma: no cover - environment dependent
                    launch_errors.append(f"{engine}: {exc}")
                    continue
            if self._browser is None:
                raise RuntimeError("; ".join(launch_errors) if launch_errors else "Unable to launch browser")
        except Exception as exc:  # pragma: no cover - depends on environment
            self._error = f"Unable to launch Playwright browser: {exc}"
            if self._playwright:
                self._playwright.stop()
            self._playwright = None
            self._browser = None

    @property
    def available(self) -> bool:
        return self._error is None and self._browser is not None

    @property
    def error(self) -> Optional[str]:
        return self._error

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def compare(self, html_path: Path, reference_image: Path) -> Dict[str, object]:
        if not self.available:
            return {
                "html": str(html_path),
                "mockup": str(reference_image),
                "status": "not_run",
                "details": self._error or "Visual comparator unavailable.",
            }

        assert self._browser is not None  # for type checker
        context = self._browser.new_context()
        page = context.new_page()

        screenshot_path = self.assets_dir / f"{html_path.stem}_render.png"
        diff_path = self.assets_dir / f"{html_path.stem}_diff.png"

        try:
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=60000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception as exc:
            context.close()
            return {
                "html": str(html_path),
                "mockup": str(reference_image),
                "status": "error",
                "details": f"Failed to capture screenshot: {exc}",
            }

        context.close()

        try:
            expected = Image.open(reference_image).convert("RGB")  # type: ignore[attr-defined]
            actual = Image.open(screenshot_path).convert("RGB")  # type: ignore[attr-defined]
        except Exception as exc:
            return {
                "html": str(html_path),
                "mockup": str(reference_image),
                "status": "error",
                "details": f"Unable to load images for comparison: {exc}",
                "screenshot": str(screenshot_path),
            }

        if actual.size != expected.size:
            actual = actual.resize(expected.size)  # type: ignore[attr-defined]

        diff = ImageChops.difference(expected, actual)  # type: ignore[attr-defined]
        stat = ImageStat.Stat(diff)  # type: ignore[attr-defined]
        rms = sum(value ** 2 for value in stat.rms) ** 0.5
        normalized = rms / (255 * (3 ** 0.5))
        match_percent = max(0.0, 100.0 * (1 - normalized))

        status = "match"
        details = ""

        if normalized > self.tolerance:
            status = "mismatch"
            enhanced = diff.point(lambda p: min(255, int(p * 4)))
            enhanced.save(diff_path)
            details = f"Visual diff exceeds tolerance ({normalized:.4f} > {self.tolerance:.4f})."
        else:
            if diff_path.exists():
                diff_path.unlink()

        result = {
            "html": str(html_path),
            "mockup": str(reference_image),
            "status": status,
            "match_percent": round(match_percent, 2),
            "screenshot": str(screenshot_path),
        }

        if details:
            result["details"] = details
            result["diff_image"] = str(diff_path)

        return result


def find_mockups(directory: Path) -> List[Path]:
    return sorted(
        [p for p in directory.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"}],
        key=lambda p: p.name.lower(),
    )


def find_html_files(directory: Path) -> List[Path]:
    return sorted(
        [p for p in directory.glob("*.html")],
        key=lambda p: p.name.lower(),
    )


def match_html(mockup: Path, html_files: List[Path]) -> Optional[Path]:
    base = mockup.stem.lower()
    for html_path in html_files:
        if html_path.stem.lower() == base:
            return html_path
    for html_path in html_files:
        if html_path.stem.lower() == "index":
            return html_path
    return html_files[0] if html_files else None


def compare_visuals(
    directory: Path,
    comparator: Optional[VisualComparator],
) -> List[Dict[str, object]]:
    images = find_mockups(directory)
    html_files = find_html_files(directory)
    results: List[Dict[str, object]] = []

    if not images:
        return results

    if not html_files:
        for image_path in images:
            results.append(
                {
                    "mockup": str(image_path),
                    "status": "no_html",
                    "details": "No HTML files found in directory for comparison.",
                }
            )
        return results

    for image_path in images:
        html_path = match_html(image_path, html_files)
        if not html_path:
            results.append(
                {
                    "mockup": str(image_path),
                    "status": "no_html",
                    "details": "Unable to locate HTML counterpart for mockup.",
                }
            )
            continue

        if comparator is None:
            results.append(
                {
                    "html": str(html_path),
                    "mockup": str(image_path),
                    "status": "not_run",
                    "details": "Visual comparison skipped (--skip-visual).",
                }
            )
            continue

        comparison = comparator.compare(html_path, image_path)
        results.append(comparison)

    return results


def process_readme(
    readme_path: Path,
    root: Path,
    args: argparse.Namespace,
    comparator: Optional[VisualComparator],
    processed_visual_dirs: set[Path],
) -> Tuple[Dict[str, object], List[Dict[str, object]], bool]:
    instructions = extract_instructions(readme_path)
    cwd = readme_path.parent
    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(root)

    success = True

    for instruction in instructions:
        command = instruction["command"]
        if not command:
            instruction["status"] = "info"
            continue

        command_str = str(command)
        allowed, reason = classify_command(command_str, root, args.allow_destructive)
        if not allowed:
            instruction["status"] = "skipped"
            instruction["details"] = reason
            success = False
            continue

        try:
            code, stdout, stderr = run_command(command_str, cwd, args.timeout, env=env)
            instruction["stdout"] = stdout
            instruction["stderr"] = stderr
            if code == 0:
                instruction["status"] = "success"
            else:
                instruction["status"] = "failed"
                instruction["details"] = f"Exit code {code}."
                success = False
        except subprocess.TimeoutExpired:
            instruction["status"] = "failed"
            instruction["details"] = f"Timed out after {args.timeout} seconds."
            success = False
        except RuntimeError as exc:
            instruction["status"] = "failed"
            instruction["details"] = str(exc)
            success = False
        except Exception as exc:  # pragma: no cover
            instruction["status"] = "failed"
            instruction["details"] = f"Unexpected error: {exc}"
            success = False

    visual_results: List[Dict[str, object]] = []
    directory = readme_path.parent

    if directory not in processed_visual_dirs:
        processed_visual_dirs.add(directory)
        visual_results = compare_visuals(directory, comparator)
        for result in visual_results:
            if result.get("status") in {"mismatch", "error"}:
                success = False

    result_payload = {
        "path": str(readme_path),
        "instructions": instructions,
    }

    return result_payload, visual_results, success


def summarize_instruction_status(instructions: List[Dict[str, object]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for instruction in instructions:
        status = str(instruction.get("status", "unknown"))
        summary[status] = summary.get(status, 0) + 1
    return summary


def html_escape(value: str) -> str:
    return html.escape(value, quote=True)


def write_html_report(
    report: Dict[str, object],
    output_path: Path,
    visual_results: List[Dict[str, object]],
) -> None:
    logs_dir = output_path.parent
    logs_dir.mkdir(parents=True, exist_ok=True)

    generated_at = html_escape(report["generated_at"])
    root = html_escape(report["root"])

    readme_sections = []
    for item in report["readmes"]:
        path = html_escape(item["path"])
        instructions = item["instructions"]
        summary = summarize_instruction_status(instructions)
        summary_json = html_escape(json.dumps(summary, indent=2))

        rows = []
        for idx, instruction in enumerate(instructions, start=1):
            text = html_escape(str(instruction["text"]))
            status = html_escape(str(instruction["status"]))
            command = html_escape(instruction["command"]) if instruction["command"] else ""
            details = html_escape(str(instruction.get("details", "")))
            stdout = html_escape(str(instruction.get("stdout", "")))
            stderr = html_escape(str(instruction.get("stderr", "")))

            output_block = ""
            if stdout or stderr:
                combined = ""
                if stdout:
                    combined += f"<strong>stdout</strong>\n{stdout}"
                if stderr:
                    if combined:
                        combined += "\n\n"
                    combined += f"<strong>stderr</strong>\n{stderr}"
                output_block = f"<details><summary>Command Output</summary><pre>{combined}</pre></details>"

            rows.append(
                f"<tr>"
                f"<td>{idx}</td>"
                f"<td>{text}</td>"
                f"<td>{command}</td>"
                f"<td>{status}</td>"
                f"<td>{details}{output_block}</td>"
                f"</tr>"
            )

        table_html = (
            f"<h2>{path}</h2>"
            f"<details open><summary>Instruction Status Summary</summary><pre>{summary_json}</pre></details>"
            f"<table>"
            f"<thead><tr><th>#</th><th>Instruction</th><th>Command</th><th>Status</th><th>Notes</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table>"
        )
        readme_sections.append(table_html)

    visual_sections: List[str] = []
    for idx, result in enumerate(visual_results, start=1):
        status = html_escape(str(result.get("status", "unknown")))
        mockup = html_escape(str(result.get("mockup", "")))
        html_page = html_escape(str(result.get("html", "")))
        details = html_escape(str(result.get("details", "")))
        match_percent = html_escape(str(result.get("match_percent", "")))
        screenshot_path = result.get("screenshot")
        diff_path = result.get("diff_image")

        screenshot_tag = f'<img src="{html_escape(Path(screenshot_path).name)}" alt="Screenshot">' if screenshot_path else ""
        diff_tag = ""
        if diff_path:
            diff_tag = f'<img src="{html_escape(Path(diff_path).name)}" alt="Diff">'

        visual_sections.append(
            f"<div class='visual-card'>"
            f"<h3>#{idx} – {status}</h3>"
            f"<ul>"
            f"<li><strong>Mockup:</strong> {mockup}</li>"
            f"<li><strong>HTML:</strong> {html_page}</li>"
            f"<li><strong>Match %:</strong> {match_percent}</li>"
            f"<li><strong>Details:</strong> {details}</li>"
            f"</ul>"
            f"{screenshot_tag}"
            f"{diff_tag}"
            f"</div>"
        )

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Project Validation Report</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        margin: 2rem;
        background: #f4f6fb;
        color: #1c2333;
      }}
      h1 {{
        margin-top: 0;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 2rem;
        background: #fff;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
      }}
      th, td {{
        border: 1px solid #d8deeb;
        padding: 0.6rem 0.75rem;
        vertical-align: top;
        text-align: left;
      }}
      th {{
        background: #eef2fb;
      }}
      details > pre {{
        background: #121826;
        color: #e8ecf7;
        padding: 0.75rem;
        overflow-x: auto;
      }}
      pre {{
        white-space: pre-wrap;
      }}
      .visual-card {{
        background: #fff;
        padding: 1rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
      }}
      .visual-card img {{
        max-width: 100%;
        height: auto;
        margin-top: 0.75rem;
        border: 1px solid #d8deeb;
      }}
    </style>
  </head>
  <body>
    <h1>Validation Report</h1>
    <p><strong>Generated:</strong> {generated_at}</p>
    <p><strong>Root:</strong> {root}</p>
    <section>
      <h2>README Execution</h2>
      {''.join(readme_sections)}
    </section>
    <section>
      <h2>Visual Regression Checks</h2>
      {''.join(visual_sections) or '<p>No mockups detected.</p>'}
    </section>
  </body>
</html>
"""

    output_path.write_text(html_body, encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser().resolve()

    if not root.exists():
        print(f"[error] Root path does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"[error] Root path is not a directory: {root}", file=sys.stderr)
        return 1

    report_path = Path(args.report) if args.report else root / "logs" / "validation_report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    assets_dir = report_path.parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    comparator: Optional[VisualComparator] = None
    if not args.skip_visual:
        comparator = VisualComparator(assets_dir, args.visual_tolerance)
        if comparator.error:
            print(f"[warn] Visual comparator unavailable: {comparator.error}", file=sys.stderr)

    readmes = find_readme_files(root)
    if not readmes:
        print(f"[warn] No README files found under {root}.")

    processed_visual_dirs: set[Path] = set()
    report_payload = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": str(root),
        "readmes": [],
    }

    all_visual_results: List[Dict[str, object]] = []
    overall_success = True

    try:
        for readme in readmes:
            readme_result, visuals, success = process_readme(
                readme,
                root,
                args,
                comparator if comparator and comparator.available else None,
                processed_visual_dirs,
            )
            report_payload["readmes"].append(readme_result)
            all_visual_results.extend(visuals)
            if not success:
                overall_success = False
    finally:
        if comparator:
            comparator.close()

    write_html_report(report_payload, report_path, all_visual_results)
    print(f"[info] Report written to {report_path}")

    return 0 if overall_success else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
