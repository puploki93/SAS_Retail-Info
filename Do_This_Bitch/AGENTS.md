# Repository Guidelines

## Project Structure & Module Organization
The front-end lives in `public/` (HTML, CSS, JS, and the JSON feeds consumed by the SPA). Source assets are normalized under `content/assets/`, grouped by channel (docs, emails, media, projects, slides, spreadsheets). Generated manifests belong in `data/`, mirroring `policies.example.yaml` and `projects/plv-2025-08-24.example.yaml`. Automation scripts stay in `scripts/`; land experiments in a feature branch before merging. Treat `SAS/` as a temporary drop-zone for newly collected field files, then migrate the curated versions into `content/assets/`. Update `PROJECT_PLAN.md` when you adjust roadmap scope or deliverables.

## Build, Test, and Development Commands
Serve the prototype locally with `python3 -m http.server --directory public 8000` and browse to http://localhost:8000. Generate a project manifest via `python3 scripts/ingest_emails.py --project-id PLV-2025-08-24 --assets-root content/assets --output data/projects/plv-2025-08-24.yaml --dry-run`; remove `--dry-run` after reviewing the preview. Emit UI-ready JSON with `python3 scripts/ingest_emails.py --project-id ... --format json --output public/data/projects.json`. Validate any edited JSON feed using `python3 -m json.tool public/data/projects.example.json`.

## Coding Style & Naming Conventions
Follow the existing two-space indentation for HTML, CSS, JS, and YAML. Keep markup semantic, and prefer kebab-case class names (e.g., `hero-overlay`). Asset filenames should be lowercase with hyphens; Python symbols stay snake_case and comply with PEP 8. When adding manifests, order keys consistently (id, title, store, contacts, travel, documents) so diffs remain readable.

## Testing Guidelines
Automated tests are pending, so rely on focused checks. After updating data, cycle through every tab in the UI and confirm dynamic sections render without console warnings. Run ingestion scripts with `--dry-run` to inspect structured output before writing files, and add or refresh `.example` fixtures whenever schemas change.

## Commit & Pull Request Guidelines
Use imperative, sentence-case commit messages around 72 characters (“Add travel manifest generator”). Reference related Jira or Trello items in the body when applicable. Pull requests should explain the change, call out touched data or assets, attach before/after screenshots for UI tweaks, and list any manual deployment steps. Request review from both a front-end maintainer and the data steward whenever you move or rename assets.

## Security & Content Handling
Only commit sanitized assets; strip PII before moving items out of `SAS/`. Never add credentials or production URLs to the repo. Delete temporary exports once normalized to keep history lean for GitHub Pages deployments.
