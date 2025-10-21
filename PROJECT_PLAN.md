# SAS Employee Hub – Implementation Playbook

This file is the go-to reference for automating the SAS Retail Employee Hub, guiding future enhancements, and deploying everything on the VPS + `sasretail.info`. When instructed to “look at the file,” use it as the authoritative checklist.

---

## 1. Current State Snapshot
- **Repo**: `SAS_Retail-Info` on GitHub (`main` branch) contains a static prototype (`index.html`, `styles.css`, `script.js`, `README.md`).
- **Local assets**: Raw onboarding/travel/policy documents and email exports live under `/Users/loki/Desktop/SAS/…`.
- **Gap**: Prototype is static; employees still receive long PDF/email chains per project. No structured data, manifests, or server automation yet.

---

## 2. Business Goal
Deliver a centralized, low-friction hub where employees can:
1. See project-critical info (schedule, travel, carpool, policies) at a glance.
2. Access authoritative attachments without rummaging through email chains.
3. Receive updates via a single link per project rather than multiple forwarded messages.

---

## 3. Content Analysis Summary
| Email Type | Pain Points | Key Data Extracted |
|------------|-------------|--------------------|
| **Carpool** (`Carpool Email example.pdf`) | All-caps policies mixed with rider list; 3-page PDF for two assignments. | Driver & passengers, arrival times, airport rules, policy reminders. |
| **Flights** (`Flights Email Example.pdf`) | Vendor itinerary buried in marketing noise; multiple legs & confirmation. | Confirmation `2MQM3C`, AUS↔SNA legs, fare details, travel dates. |
| **Hotel** (`Hotels email example.pdf`) | Repetitive per-room confirmations; important bits hidden. | Hotel address, check-in/out, reservation numbers per employee, cancellation rules. |
| **Schedule** (`(PLV) SCHEDULE INFO…pdf`) | 17 pages mixing instructions, rosters, forwarded policies, attachments list. | Store ID, address, report time (1:45 AM), roster, contacts, policies, attachments. |
| **Policies** | Duplicated in every email; crucial but overwhelming. | Dress code (no facial piercings/tattoos), smoking ban, PROD reporting expectations. |

Core conclusion: Each project generates 4+ verbose emails with redundant policy blocks and vendor formatting. Employees only need a concise summary plus authoritative attachments.

---

## 4. Target Architecture
```
SAS_Retail-Info/
├── data/
│   ├── projects/
│   │   └── <project-id>.yaml      # structured project manifest
│   └── policies.yaml              # evergreen policy references
├── content/
│   ├── assets/                    # PDFs, emails, media (organized subfolders)
│   └── templates/                 # optional layouts or partials
├── public/
│   ├── index.html                 # generated or static homepage
│   └── projects/<id>.html         # per-project pages (static or generated)
├── scripts/
│   └── ingest_emails.py           # parser to update manifests from source PDFs
├── src/                           # future React/Vite/Svelte/etc if needed
├── README.md
└── PROJECT_PLAN.md                # this playbook
```

---

## 5. Implementation Roadmap

### Phase A – Data Foundation
1. **Asset Migration**
   - Mirror `/Users/loki/Desktop/SAS` structure into repo under `content/assets/<category>/`.
   - Clean filenames (no double spaces, consistent casing).
2. **Manifest Creation**
   - For each project email set, create `data/projects/<project-id>.yaml` capturing:
     ```yaml
     id: PLV-2025-08-24
     title: Playa Vista CA Remodel
     store:
       number: 10536
       address: "12746 Jefferson Blvd, Playa Vista, CA 90094"
       report_time: "2025-08-26T01:45:00-07:00"
     contacts:
       supervisor: { name: "Jessica Gamez", phone: "802-917-3329", email: "jessica.gamez@sasretailservices.com" }
       lead: { name: "Daniel Augsburger", phone: "760-336-6822", email: "daniel.augsburger@sasretailservices.com" }
       elite: { name: "Mary Franco", phone: "408-648-3964", email: "marylou.franco@sasretailservices.com" }
     travel:
       flights: [ ... legs ... ]
       hotel: { name: "Best Western Plus", check_in: "2025-06-02", check_out: "2025-06-06", reservations: [ ... ] }
       carpool: [ { driver: "Robert Noriega", riders: ["Dillon Dority"], arrival: "2025-05-27T16:20-07:00" } ]
     policies:
       references: ["dress-code", "travel-policy", "hotel-etiquette"]
     attachments:
       - title: "Merchandiser Guide"
         path: "content/assets/docs/Timekeeping Change - Merchandiser Guide.pdf"
         type: pdf
         mandatory: true
     required_actions:
       - "Contact designated driver 24h before flight."
       - "Report travel time in PROD immediately upon arrival."
     last_updated: "2025-10-21T16:00:00Z"
     ```
   - `data/policies.yaml` houses policy metadata (title, description, file path, last_updated).

3. **Parser Script**
   - Implement `scripts/ingest_emails.py` to:
     - Parse PDFs (`PyPDF2`) to extract structured data.
     - Populate or update YAML manifests.
     - Log discrepancies for manual review.
   - Optional: accept raw `.eml` to preserve headers (subject = unique project id).

### Phase B – Front-end Upgrade
1. Refactor the static prototype to read manifests (either:
   - Static-site generator: run script to build HTML pages into `public/`, or
   - Client-side fetch of JSON (converted from YAML at build time) and render with vanilla JS.
2. Implement sections per project:
   - **Highlights**: report time, store address, key contacts.
   - **Checklist**: required actions with acknowledgment toggles (persist to localStorage initially).
   - **Travel/Lodging**: tables summarizing flights, hotel rooms, carpool assignments.
   - **Policies**: link cards referencing `policies.yaml`.
   - **Attachments**: filtered downloads with tags (Policy, Travel, Onboarding).
3. Add filters (Everyone / Drivers / Travelers / Supervisors) and global search across project manifests.

### Phase C – Automation & Delivery
1. **GitHub Workflow**
   - Create `.github/workflows/deploy.yml`:
     - Trigger on push to `main`.
     - SSH into VPS (reusable deploy key) to run `./scripts/deploy.sh`.
     - `deploy.sh` pulls latest repo, runs build (if any), syncs `public/` to `/srv/sasretail/www`.
2. **VPS Setup**
   - Create dedicated user/group (`deploy`, `sasretail`).
   - Clone repo under `/srv/sasretail/app`.
   - Serve `/srv/sasretail/www` via Nginx (TLS via Certbot).
   - Configure log rotation and health check (optional systemd timer).
3. **Content Delivery**
   - Optionally expose `/srv/sasretail/assets/uploads` via SFTP for leadership to drop new PDFs.
   - Add cron or webhook to trigger `ingest_emails.py` when new assets arrive.
4. **Notifications**
   - (Future) Send project update digest via email/SMS using manifest data.

---

## 6. Domain Configuration (`sasretail.info`)
1. **DNS**
   - Set `A` record (root) to VPS IPv4.
   - Add `AAAA` if IPv6 available.
   - `CNAME` for `www` → `sasretail.info` (or to Pages host if using GitHub Pages).
2. **Nginx Server Block**
   ```nginx
   server {
     server_name sasretail.info www.sasretail.info;
     root /srv/sasretail/www;
     index index.html;

     location / {
       try_files $uri $uri/ =404;
     }
     access_log /var/log/nginx/sasretail.access.log;
     error_log  /var/log/nginx/sasretail.error.log;
   }
   ```
3. **TLS**
   ```
   sudo certbot --nginx -d sasretail.info -d www.sasretail.info
   sudo systemctl reload nginx
   ```

---

## 7. Access Control & Collaboration
- **Repo**: GitHub remains source of truth. VPS uses deploy key (read-only) or service account (read/write for scripts).
- **Server Access**:
  - Add collaborators’ SSH keys to `/home/deploy/.ssh/authorized_keys`.
  - For SFTP-only access, create separate users with `ForceCommand internal-sftp` and `ChrootDirectory`.
- **Directory Permissions**:
  - `/srv/sasretail/app` – repo clone (deploy user).
  - `/srv/sasretail/www` – built static site.
  - `/srv/sasretail/assets` – shared docs; group writable.

---

## 8. Operational Playbook
1. **Adding a Project**
   - Drop raw PDFs/emails into `content/assets/projects/<project-id>/`.
   - Run `python scripts/ingest_emails.py --project <project-id>`.
   - Review/update generated `data/projects/<project-id>.yaml`.
   - Commit & push; pipeline deploys.
2. **Updating Policies**
   - Replace file in `content/assets/policies/`.
   - Update metadata in `data/policies.yaml`.
   - Note change in changelog (optional).
3. **Onboarding Teammates**
   - Share GitHub repo and this `PROJECT_PLAN.md`.
   - Provide SSH access as needed.
4. **Disaster Recovery**
   - GitHub retains history.
   - Configure nightly VPS backup of `/srv/sasretail` (rsync or snapshot).

---

## 9. Suggested Enhancements (Backlog)
- Build admin UI for manifests (form-driven editing).
- Integrate authentication (role-based content).
- Store acknowledgments (checklist completions) in a database.
- Add analytics (page visits, download counts).
- Automate PDF-to-text conversion for better search.

---

## 10. Next Immediate Actions
1. Create `data/`, `content/assets/`, `scripts/` scaffolding.
2. Write initial manifest for the Playa Vista project using existing PDFs.
3. Prototype markdown-to-HTML generation or client-side rendering.
4. Prepare VPS deployment script and GitHub Action template.
5. Move raw documents from Desktop into repo or designated server storage.

Once the server is ready, revisit this plan, execute the steps in order, and the deployment will be smooth. Use this document to keep efforts aligned across domains, repos, and collaborators.

---

**Remember:** This playbook is the single source of truth for project operations. Update it whenever major process changes occur.
