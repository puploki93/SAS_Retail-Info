#!/usr/bin/env python3
"""Utility helpers for turning archived project emails into starter manifests.

This script is intentionally lightweight—it scans the normalized asset folders,
identifies project email PDFs/EMLs, and emits a structured starter manifest in
either YAML or JSON. Think of it as scaffolding; humans still review and enrich
what it generates before publishing to production.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback when PyYAML is absent
    yaml = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root(script_path: Path) -> Path:
    """Return the repository root assuming this file lives in scripts/."""
    return script_path.resolve().parents[1]


def _humanize_slug(value: str) -> str:
    value = value.replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in value.split())


def _guess_email_type(path: Path) -> str:
    stem = path.stem.lower()
    if "carpool" in stem:
        return "carpool"
    if "flight" in stem:
        return "flights"
    if "hotel" in stem:
        return "hotel"
    if "schedule" in stem:
        return "schedule"
    if "welcome" in stem:
        return "welcome"
    if "ready" in stem:
        return "orientation"
    return "reference"


def _core_attachment_refs() -> List[Tuple[str, str, bool]]:
    """Canonical docs worth linking on almost every project."""
    return [
        ("docs/advantage-travel-policy-2025-04-14.pdf", "Advantage Travel Policy", True),
        ("docs/timekeeping-change-merchandiser-guide.pdf", "Merchandiser Timekeeping Guide", True),
        ("docs/travel-policy-call-outs.pdf", "Travel Policy Call Outs", True),
        ("docs/leads-or-elites-cannot-report-your-time.pdf", "Time Reporting Responsibilities", True),
        ("docs/to-call-or-email.pdf", "Communication Guide", False),
    ]


def _collect_attachments(assets_root: Path) -> List[Dict[str, object]]:
    attachments: List[Dict[str, object]] = []
    for rel_path, title, mandatory in _core_attachment_refs():
        absolute = assets_root / rel_path
        if absolute.exists():
            attachments.append(
                {
                    "title": title,
                    "path": absolute.relative_to(_repo_root(Path(__file__)) ).as_posix(),
                    "type": absolute.suffix.lstrip("."),
                    "mandatory": mandatory,
                }
            )
    return attachments


def _collect_source_emails(project_dir: Path) -> List[Dict[str, object]]:
    emails: List[Dict[str, object]] = []
    if not project_dir.exists():
        return emails
    for path in sorted(project_dir.glob("**/*")):
        if path.is_file() and path.suffix.lower() in {".pdf", ".eml"}:
            emails.append(
                {
                    "type": _guess_email_type(path),
                    "path": path.relative_to(_repo_root(Path(__file__)) ).as_posix(),
                }
            )
    return emails


def _dump_yaml(data: Dict[str, object]) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, indent=2, sort_keys=False)

    def _stringify(value, indent: int = 0) -> List[str]:
        pad = " " * indent
        if isinstance(value, dict):
            lines: List[str] = []
            for key, val in value.items():
                if isinstance(val, (dict, list)):
                    lines.append(f"{pad}{key}:")
                    lines.extend(_stringify(val, indent + 2))
                else:
                    lines.append(f"{pad}{key}: {val if isinstance(val, (int, float)) else json.dumps(val)}")
            return lines
        if isinstance(value, list):
            lines: List[str] = []
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(f"{pad}-")
                    lines.extend(_stringify(item, indent + 2))
                else:
                    rendered = item if isinstance(item, (int, float)) else json.dumps(item)
                    lines.append(f"{pad}- {rendered}")
            return lines
        rendered = value if isinstance(value, (int, float)) else json.dumps(value)
        return [f"{pad}{rendered}"]

    return "\n".join(_stringify(data)) + "\n"


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def build_manifest(args: argparse.Namespace, repo_root: Path) -> Dict[str, object]:
    project_id = args.project_id
    assets_root = (repo_root / args.assets_root).resolve()
    project_slug = args.project_slug or project_id.lower()
    project_dir = assets_root / "projects" / project_slug / "emails"

    manifest: Dict[str, object] = {
        "id": project_id.upper(),
        "title": args.title or _humanize_slug(project_slug),
        "store": {
            "number": args.store_number or "00000",
            "name": args.store_name or "TBD Store Name",
            "address": args.store_address or "Provide the full street address",
            "report_time": args.report_time or "YYYY-MM-DDTHH:MM:SS-07:00",
        },
        "contacts": {
            "supervisor": {
                "name": args.supervisor_name or "Supervisor Name",
                "phone": args.supervisor_phone or "+1-000-000-0000",
                "email": args.supervisor_email or "supervisor@example.com",
            },
            "lead": {
                "name": args.lead_name or "Lead Name",
                "phone": args.lead_phone or "+1-000-000-0000",
                "email": args.lead_email or "lead@example.com",
            },
        },
        "travel": {
            "flights": [],
            "hotel": {
                "name": args.hotel_name or "Hotel TBD",
                "address": args.hotel_address or "Provide hotel address",
                "check_in": args.hotel_check_in or "YYYY-MM-DD",
                "check_out": args.hotel_check_out or "YYYY-MM-DD",
                "reservations": [],
            },
            "carpool": [],
        },
        "policies": {"references": ["dress-code", "travel-policy", "time-reporting"]},
        "required_actions": [
            "Review travel policy and confirm itineraries.",
            "Contact assigned driver 24h prior to departure.",
            "Submit PROD time immediately after each shift.",
        ],
        "attachments": _collect_attachments(assets_root),
        "source_emails": _collect_source_emails(project_dir),
        "last_updated": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "notes": [
            "Generated via scripts/ingest_emails.py; review before publishing.",
            "Populate travel.flights, travel.hotel.reservations, and travel.carpool with confirmed details.",
        ],
    }

    if not manifest["attachments"]:
        manifest["attachments"] = [
            {
                "title": "Update docs under content/assets/docs before publishing",
                "path": "content/assets/docs",
                "type": "folder",
                "mandatory": False,
            }
        ]

    if not manifest["source_emails"]:
        manifest["source_emails"].append(
            {
                "type": "schedule",
                "path": f"content/assets/projects/{project_slug}/emails",
            }
        )

    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True, help="e.g. PLV-2025-08-24")
    parser.add_argument("--project-slug", help="Directory name under content/assets/projects")
    parser.add_argument("--title", help="Human-friendly project title")

    parser.add_argument("--store-number")
    parser.add_argument("--store-name")
    parser.add_argument("--store-address")
    parser.add_argument("--report-time", help="ISO8601 timestamp with timezone offset")

    parser.add_argument("--supervisor-name")
    parser.add_argument("--supervisor-phone")
    parser.add_argument("--supervisor-email")
    parser.add_argument("--lead-name")
    parser.add_argument("--lead-phone")
    parser.add_argument("--lead-email")

    parser.add_argument("--hotel-name")
    parser.add_argument("--hotel-address")
    parser.add_argument("--hotel-check-in")
    parser.add_argument("--hotel-check-out")

    parser.add_argument("--assets-root", default="content/assets", help="Relative path to assets directory")
    parser.add_argument("--output", help="Where to write the manifest; defaults to data/projects/<slug>.yaml")
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print output instead of writing file")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = _repo_root(Path(__file__))
    manifest = build_manifest(args, repo_root)

    if args.output:
        output_path = Path(args.output)
    else:
        project_slug = args.project_slug or args.project_id.lower()
        output_path = repo_root / "data" / "projects" / f"{project_slug}.yaml"

    if args.format == "json":
        rendered = json.dumps(manifest, indent=2)
    else:
        rendered = _dump_yaml(manifest)

    if args.dry_run:
        sys.stdout.write(rendered)
        return 0

    output_path = output_path if output_path.is_absolute() else (repo_root / output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote manifest to {output_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
