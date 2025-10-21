# SAS Employee Hub

Modern, SharePoint-inspired employee portal prototype for SAS Retail. The single-page web app provides tabbed navigation across core resource categories with a polished blue-gray corporate theme.

## Features
- Responsive layout with hero banner, sticky navigation, and tabbed content.
- Cards, search demo, and preview areas tailored to New Hire, Docs, Travel, and Policies hubs.
- Accessible keyboard/tab navigation and semantic markup to ease future expansion.
- Pure HTML, CSS, and vanilla JavaScript for easy deployment to GitHub Pages or static hosts.

## Getting Started
1. Clone the repo: `git clone git@github.com:puploki93/SAS_Retail-Info.git`
2. Open `public/index.html` in any modern browser to explore the prototype locally.
3. Update the static copy or sample data files to point at new assets as they become available.

### Project Structure
```
.
├── public/
│   ├── index.html          # Main application shell with tabbed sections
│   ├── script.js           # Navigation and simple demo interactions
│   └── styles.css          # Styling, layout, and responsive design rules
├── content/
│   └── assets/
│       ├── docs/           # Normalized PDF references (policies, guides, etc.)
│       ├── emails/         # Archived EML exports
│       ├── media/          # Video or audio assets
│       ├── slides/         # Slide decks and presentations
│       ├── spreadsheets/   # XLSX payroll and planning resources
│       └── projects/
│           └── plv-2025-08-24/
│               └── emails/ # Project-specific email PDFs sourced from field ops
├── data/
│   ├── policies.example.yaml   # Sample policy manifest
│   └── projects/
│       └── plv-2025-08-24.example.yaml   # Sample project manifest structure
├── scripts/                # Automation stubs and future ingestion tooling
└── PROJECT_PLAN.md         # Implementation playbook / source of truth
```

### Sample Data Files
- `data/projects/plv-2025-08-24.example.yaml` demonstrates how to capture store, travel, contacts, and attachment metadata for a deployment.
- `data/policies.example.yaml` provides reference entries that map policy IDs to the normalized assets in `content/assets`.
- Duplicate these examples, adjust IDs, and point to real assets before publishing manifests to production.

### Tooling & Build Hooks
- `scripts/ingest_emails.py` seeds a starter manifest by scanning the normalized asset folders:
  ```bash
  scripts/ingest_emails.py \
    --project-id PLV-2025-08-24 \
    --project-slug plv-2025-08-24 \
    --output data/projects/plv-2025-08-24.yaml
  ```
  The `--format json` and `--dry-run` flags are available for quick previews or to emit JSON alongside YAML.
- The front-end consumes static JSON feeds under `public/data/`. Regenerate these (or convert YAML → JSON during a future build step) so the UI reflects the latest manifests and policy catalog.

## Deployment
The repository is ready for GitHub Pages or any static hosting platform. Publish by serving `index.html` and the accompanying assets at the site root.

To update the live site:
1. Make your changes locally.
2. Commit with a descriptive message.
3. Push to `main`: `git push origin main`

## Roadmap Ideas
- Upload workflow for documents and travel receipts.
- Role-based dashboards (Supervisor, Operations) and personalization.
- Authentication integration for access control, employee profiles, and approvals.
- Replace icons with branded artwork and embed live documents/videos.

## License
Copyright © 2025 SAS Retail.
