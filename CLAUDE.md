# ITCA Portal — Project Summary

**Client:** IT Certification Academy (ITCA)
**Campuses:** Durban (DBN), Pietermaritzburg (PMB)
**Stack:** Django 5 (MVT) + PostgreSQL + Docker + TailwindCSS v4 + Microsoft Entra ID (planned)
**Deployment target:** Azure

---

## 1. Business Overview

ITCA runs two campuses offering two programs — **Cyber Security** and **Software Development**. The portal manages the full student lifecycle: application, admission, enrollment, module assignment, local and international assessment, promotion, and eventual alumni status.

### User Roles

| Role | Responsibility |
|---|---|
| **Exec Admin** | Super user. Approves/rejects applications, manages campuses/programs/modules/classes, views all data. |
| **Test Admin** | Records international certification exam attempts and results (CompTIA, Microsoft, etc). |
| **Trainer** | Grades local NQF5 assessments, views student international exam results. Promotion to the next cohort happens automatically once a student passes every NQF5 assessment — there is nothing for the Trainer to request. |
| **Data Capturer** | Creates applicant profiles and submits them for Exec Admin approval. Can see all applications (including drafts) to prevent duplicate submissions. |

---

## 2. Core Business Flow

```
1. Data Capturer creates an Applicant profile (multi-step draft form)
       ↓
2. Applicant submitted for review (status: Pending)
       ↓
3. Exec Admin reviews application
       ↓
   ┌───────────────┴───────────────┐
   ↓                               ↓
Approve                         Reject
   ↓                          (capacity reached —
System finds active Class      only valid reason)
for program+campus+year            ↓
   ↓                          Retained 1 year,
No active class?              then purged
   → BLOCK, must create class
   first
   ↓
Class at capacity?
   → BLOCK, must increase
   capacity or add class
   ↓
Student record created
(auto-generated Student ID
e.g. DBN-2026-001)
   ↓
Enrollment created (linked to Class)
   ↓
Signal fires: default modules
assigned via ProgramModule
(is_default=True)
   ↓
Signal fires: LocalAssessment
slots created per module
(2 Formative + 1 Summative, empty)
   ↓
Trainer grades formatives (95% pass mark,
1 remediation attempt allowed) and
summatives (Competent / Not Yet Competent)
   ↓
Student's formative average ≥ 94%
→ deemed Competent overall (dashboard/reporting metric)
   ↓
Every NQF5 assessment passed
(both formatives ≥95%, summative Competent,
across every assigned module)
   ↓
AUTOMATIC: New → Returning cohort
(no Trainer request, no Exec Admin approval —
old enrollment marked Promoted, new Active
enrollment created the moment full pass is
detected, if a Returning class already exists)
   ↓
Eventually: Graduation → Alumni record created
```

---

## 3. Key Business Rules Implemented

- **POPI consent is optional** — recorded but never blocks submission (South African law does not permit withholding service over non-essential consent).
- **Applicant reference number** — auto-generated on creation: `ITCA-YYYY-XXXXX`.
- **Student ID** — auto-generated on approval: `{CAMPUS_CODE}-{YYYY}-{SEQUENCE}`, sequence resets per campus per year, e.g. `DBN-2026-001`.
- **Duplicate applicant detection** — matched on ID number. Data Capturer sees a warning banner with the existing application's reference before submitting a new one.
- **Class capacity is hard-tracked** — a numeric `capacity` field on `Class`. Approval is blocked if the class is full or does not exist yet.
- **Modules are decoupled from programs** via a `ProgramModule` junction table (`is_default` flag controls auto-assignment). A single module (e.g. Security+) can belong to multiple programs.
- **Default module assignment is a snapshot** — changing defaults only affects future students, never existing ones.
- **Local assessment structure** — each module has exactly 2 Formative assessments (95% pass mark) and 1 Summative assessment (Competent / Not Yet Competent), auto-created (empty) the moment a student is assigned a module.
- **Remediation** — a Formative mark below 95% can be remediated once; the remediation mark becomes final and is the only mark used in averages going forward.
- **Overall student competency** — average of all *effective* formative marks (remediation mark if remediated, else original mark) across every module. **≥ 94% average = Competent.**
- **Rejection reason is fixed** — the only valid rejection reason is campus capacity being full (no free-text reason field).
- **Rejected/unsuccessful applications** are retained for exactly one year before purging (not yet implemented — see Outstanding Work).

---

## 4. Architecture

### Django Apps

| App | Responsibility |
|---|---|
| `accounts` | Custom `SystemUser` model (replaces Django's default User). Entra ID auth via `mozilla-django-oidc`. Role and campus assignment. |
| `academics` | Campus, Program, Module, ProgramModule (junction), Class, Enrollment. Settings UI for Exec Admin lives here. |
| `admissions` | Applicant, StudentContact (next of kin), Student, Alumni. The application/registration multi-step form workflow. |
| `assessments` | StudentModule, LocalAssessment, InternationalExamAttempt, ExamBooking, AccessKey, LearningPlatformCredential. |
| `dashboard` | Exec Admin dashboard aggregation view (stat cards, student table, pass rate donut chart). |

### Authentication

- Custom user model (`accounts.SystemUser`) — set as `AUTH_USER_MODEL` from project start (cannot be changed after first migration).
- No local passwords for regular users — `set_unusable_password()` on creation.
- Authentication planned via Microsoft Entra ID (Azure AD) using `mozilla-django-oidc`. **Not yet configured — Azure App Registration details outstanding.**
- Django admin login uses `ModelBackend` (email + password) for emergency/superuser access only.
- Dual `AUTHENTICATION_BACKENDS`: `ModelBackend` (admin) + `OIDCAuthenticationBackend` (SSO, pending setup).

### Infrastructure

- **Local dev:** Docker Compose runs PostgreSQL only (port 5433 externally to avoid conflict with a locally installed Postgres, mapped to 5432 internally).
- **Django app:** runs locally via `venv`, not yet containerized (planned before Azure deployment).
- **TailwindCSS v4:** compiled locally via `@tailwindcss/cli`, no `tailwind.config.js` (v4 uses `@theme` in CSS directly). Watch process runs in a separate terminal (`npm run tailwind:watch`).
- **Static files:** `static/css/output.css` is the compiled Tailwind output, referenced in `base.html`.

---

## 5. What Has Been Built

### ✅ Database Schema
- Custom `SystemUser` model with role-based permission helpers (`is_exec_admin`, `is_trainer`, etc.)
- Full academics schema: Campus, Program, Module, ProgramModule, Class (with `capacity`), Enrollment
- Full admissions schema: Applicant (with auto-generated `application_reference` and `referral_source`), StudentContact, Student (with auto-generated `student_id_code`), Alumni
- Assessments schema: StudentModule (with `assignment_type`: Default/Elective), LocalAssessment (redesigned for 2 Formative + 1 Summative per module), InternationalExamAttempt, ExamBooking, AccessKey, LearningPlatformCredential

### ✅ Automated Business Logic (Signals)
- `assign_default_modules` — fires on `Student` creation, snapshots current `ProgramModule` defaults into `StudentModule` records
- `create_local_assessment_slots` — fires on `StudentModule` creation, creates the 3 empty assessment records (PFA01, PFA02, PSA)
- `auto_promote_on_full_nqf5_pass` — fires on every `LocalAssessment` save, promotes a student from their active New-cohort enrollment to a Returning class the moment `Student.all_nqf5_passed` goes true (see "Automatic Promotion" below)

### ✅ Exec Admin Dashboard (`/dashboard/`)
- Stat cards: Pending Applications, New Registrations, Active Students, per-program counts
- Student data table with Program/Trainer filters
- Pass rate donut chart (SVG, no JS chart library)
- Matches the approved mockup design

### ✅ Admissions Workflow
- 5-step application form (Personal → Contact & Address → Education & Disability → Next of Kin → Review) with a visual stepper
- Draft saving at every step
- Duplicate ID number detection with a warning banner showing the existing application
- Applications list view (filterable by status) — visible to Data Capturers and Exec Admins
- Application detail/review view for Exec Admin
- Approve workflow: finds active class → checks capacity → creates Student + Enrollment → triggers default module assignment
- Reject workflow: fixed reason (capacity reached), retains record

### ✅ Historical Student Onboarding (`/admissions/applications/onboard/`)
- A second entry point into the same 4-step form (Personal → Contact & Address → Education & Disability → Next of Kin) for backfilling students who already exist in real life, as distinct from a fresh admission going through a Pending → Exec-Admin-review decision
- `Applicant.is_historical_onboarding` is set once, at creation, from the URL that started the flow (`onboard_new` vs `application_new`) and persists on the row from then on — re-editing an earlier step of an in-progress draft can't accidentally flip it back
- Step 5 branches on that flag: a historical record shows "Assign to class" (any active class in the applicant's program/campus, any cohort or academic year, plus a start date) instead of "Submit for approval" — there's no admission decision to make for someone who already exists, so `onboard_confirm` creates the Student + Enrollment directly (still capacity-checked) rather than going through the Pending/Approve gate
- Accessible to Data Capturers and Exec Admins, same permission as a normal application

### ✅ Student Profile Enhancements (`/admissions/students/<id>/`)
- Student email is now editable inline from the profile header, Exec Admin only — rejects a duplicate with a clear message rather than a raw `IntegrityError` (the field is unique)
- A "Demographic Details" section (date of birth, gender, nationality, ID type, residential status, disability status, education, contact/address, referral source, POPIA consent) renders as a native `<details>`/`<summary>` element, collapsed by default
- Student list search (`?q=`) now matches first name and last name in addition to Student ID — previously ID-only

### ✅ Settings Page (`/academics/settings/`)
- Tabbed interface: Campuses, Programs, Modules (+ Program-Module linking), Classes
- Add/edit forms for each entity
- Exec Admin-only access via `@exec_only` decorator

### ✅ Design System — "Redesign v6" (replaced the flat/"Modernist" theme)
- Superseded the flat/light "Modernist" theme (sharp corners, Archivo, solid borders) entirely, implementing the `ITCA Redesign v6.dc.html` canvas imported from `claude.ai/design` — Inter typography, rounded cards (`0.625rem` radius) with soft drop shadows instead of flat bordered panels, and a navy→blue gradient hero banner (`.surface-hero`) at the top of every main portal screen
- `static/css/source.css` tokens now: `--color-itca-navy` (#0f172a), `--color-itca-blue`/`-light`/`-dark` (#2563eb family), `--color-itca-cyan` (#0ea5e9, Cyber Security accent), `--color-itca-purple` (#8b5cf6, Software Dev accent), `--color-itca-green`/`-amber`/`-red` (+`-light`/`-dark`) for status colours, `--color-itca-bg` (#f7f8fa), `--color-itca-surface` (#f1f5f9), `--color-itca-border` (#e2e8f0)
- The old blanket "force every `rounded-*` utility to 0" rule is gone — rounded corners are back everywhere, no override needed
- Component classes: `.surface`/`.surface-soft`/`.surface-nav` (white rounded panels with shadow), `.surface-hero` (gradient hero banner with a faint dot-grid overlay via `::before`), `.stat-card`, `.dash-table`, `.filter-pill`, `.badge`/`.badge-blue`/`-green`/`-amber`/`-red`/`-slate`/`-purple` (new — status/role/type pill chips), `.avatar` (new — gradient initials circle used in every table/card listing a person), `.btn-primary`/`.btn-secondary` (new)
- `base.html`'s `<main>` wraps `{% block main_class %}` (default: the old centred `max-w-screen-xl mx-auto px-6 py-8` container) — pages built around a full-bleed gradient hero (dashboard, settings, users, trainers, reports, grading, exams, attendance, bookings) override it to empty and lay out their own hero + padded sections; templates that haven't been individually rebuilt around a hero yet keep the default padded container and pick up the new look for free through the shared component classes above
- Primary buttons: `.btn-primary` (`bg-itca-blue text-white`, rounded). Status badges: `.badge-*` pairing (never bare `text-itca-blue` inside a green badge or vice versa)
- `static/images/backdrops/` still holds `turqoise.jpg` (unused) and `cloud.png` (reused as the landing page hero illustration — the canvas's own `vectorelements-*.png` illustration asset was never added to the repo)
- ITCA logo integrated into navbar; `static/images/favicon.png` (cropped icon mark) used as the favicon
- **Fully restyled to v6**: landing/sign-in (`accounts/landing.html`, now a split two-panel layout), dashboard (`dashboard/index.html`, gradient hero + overlapping stat cards), Users list (add/invite button), and every screen that only needed the shared component classes to pick up the new look (Settings, Students, Grading, Exams)
- **Also rebuilt with the v6 hero + tab-strip layout**: Settings (tabs now sit inside the gradient hero), Grading (real "NQF5 Assessments / Int. Certifications / Attendance" tab strip — Int. Certifications is a new read-only view at `assessments:trainer_intcert`, Attendance links to the register), Exam Results (hero + "Exam Results / Bookings" tab strip), Bookings (now has an actual month calendar grid with prev/next navigation, plus the upcoming list)
- **Not yet rebuilt to the mockup's exact visual treatment** (functionally complete, just plainer): Exam Results is still a flat filterable table rather than the mockup's expandable per-student card list — reworking that would mean regrouping the underlying query by student, a bigger change than a style pass

### ✅ New backend features added to support Redesign v6 screens that had no prior model/view
- **Attendance** (`academics.AttendanceRecord`, `/attendance/`, Trainer-only) — one row per student per day (Present/Late/Absent + time-in + notes) for the trainer's own active class; a record is auto-created defaulting to Present the first time a date is opened so the trainer only edits exceptions. MTD attendance rate computed per student per month.
- **Trainer roster** (`accounts:trainer_list`, `/trainers/`, Exec Admin-only) — card grid of every Trainer with active student count and formative pass rate, computed live from `Student.formative_average`/`is_competent` (no new stats model needed)
- **Reports** (`dashboard:reports`, `/dashboard/reports/`, Exec Admin-only) — NQF5 pass rate by program and certification pass rate by module, aggregated live from existing `LocalAssessment`/`InternationalExamAttempt` data
- **Exam Bookings** (`assessments.ExamBooking`, `/assessments/bookings/`, Test Admin-only) — schedules a future exam sitting (date/time) against a `StudentModule`, distinct from `InternationalExamAttempt` which records the actual result once sat; a booking can optionally link forward to the attempt that resulted from it
- **User invite** (`accounts:user_invite`, `/accounts/users/invite/`) — lets an Exec Admin pre-create a `SystemUser` (unusable password, same as Entra auto-provisioning) ahead of that person's first Microsoft sign-in, rather than only being able to edit a role after their first login
- Both migrations (`academics.0004_attendancerecord`, `assessments.0004_exambooking`) are **applied to the live local DB** — verified via `showmigrations`, `makemigrations --check` (no drift), and a direct `\d` on both tables in `psql` confirming columns/FKs match the models exactly. Every restyled/new view was also smoke-tested with Django's test `Client` against real DB users (exec admin, test admin, a temporary trainer created and rolled back) — all returned 200.
- Exam Results (`assessments:exam_attempt_list`) was reworked from a flat table into the mockup's expandable per-student card list — `exam_attempt_list` view now also builds `grouped_attempts` (attempts bucketed by student, with passed/failed counts) alongside the original flat `attempts` queryset so both the card list and any future flat view stay in sync.
- **Schema documentation**: a full ER diagram + per-table column/FK reference, reverse-engineered directly from Postgres's `information_schema` (not copied from `models.py`), was published as an artifact — see "ITCA Schema Atlas" in this session's artifacts. Covers all 19 domain tables across the four apps, with the two new tables called out.

### ✅ Trainer Grading Interface (`/assessments/grading/`)
- Table view: Student ID, Name, Cohort, Module, PFA01/PFA02/PSA columns, scoped to the logged-in trainer's own students only
- Click a row → popup tile for entering formative marks (with remediation, enforced server-side to require an original mark below 95%) or summative competency
- Popup only closes on a confirmed successful save from the server
- IDOR-protected: a trainer cannot grade another trainer's student via a guessed URL

### ✅ Student List and Detail View (`/admissions/students/`)
- Filters: Campus, Program, Cohort, Trainer (Exec Admin only); search by Student ID
- Detail view: profile, modules with local assessment marks, enrollment history (a `Promoted` row followed by a new `Active` row in this same table is a student's promotion history — see "Automatic Promotion" below)
- Exec Admin sees every student; Trainers see only their own (IDOR-protected)

### ✅ Test Admin Interface (`/assessments/exams/`)
- Records international exam attempts, restricted to modules with `is_international_assessment=True`
- `attempt_number` computed server-side (never trusted from the client)
- Filterable history by module and Pass/Fail

### ✅ Automatic Promotion (replaced the manual Promotion workflow)
- **The manual Trainer-requests / Exec-Admin-approves Promotion workflow has been removed entirely** — no more "Promotions" nav link, views, URLs, templates, or `Promotion` model/table (migration `assessments.0005_delete_promotion` drops it from the live DB). This was a deliberate client instruction, not a simplification made unprompted.
- **Promotion is now fully automatic**: a `post_save` signal on `LocalAssessment` (`assessments/models.py`) checks `Student.all_nqf5_passed` (admissions/models.py) — a stricter, all-or-nothing check than the dashboard's `is_competent` average — after every mark is saved. It's true only once *every* local NQF5 assessment the student has (both formatives ≥95%, using the remediation mark where one was used, and the summative marked Competent) is passed, across every module they're assigned.
- The moment that flips true for a student on an active **New**-cohort enrollment, the same signal atomically marks the old enrollment `Promoted` (with an end date) and creates a new `Active` enrollment in the matching **Returning** class for that program/campus/current year — following the student's trainer across if the Returning class has a different one. If no such Returning class exists yet, the student is left as-is and the check simply re-runs (and succeeds) the next time a mark is edited after an Exec Admin creates one.
- Idempotent by construction: once promoted, the student's active enrollment is no longer New-cohort, so the signal no-ops on every subsequent grade edit — no risk of double-promotion.
- `admissions/views.py`'s `student_detail` view and template no longer show a separate "Promotion History" table or a "Request Promotion" button — a `Promoted` row followed by a new `Active` row in the existing Enrollment History table on that page *is* the promotion history now.
- Verified end-to-end in a rolled-back transaction: created a student, graded both formatives and the summative for one module, confirmed the enrollment flipped to `Promoted`, a new `Active` enrollment appeared in the Returning class, and the student's trainer followed to the new class's trainer.

### ✅ Dashboard Redesign — International Exams elevated, NQF5 removed
- **The NQF5 Assessments table and its Summative-competency donut were removed from the dashboard entirely** — pairing a formative-average donut against a mixed NQF5/international table never made clean sense as a metric, per client feedback. `Student.formative_average`/`is_competent` are unaffected everywhere else (Reports page, auto-promotion) — this was a dashboard-only removal.
- **International Exam Attempts elevated** into that table's former primary position (2/3 width) — now shows each student's most recent attempt (module, score, Passed/Failed), not just a raw percentage. The "most recent" lookup breaks ties on `attempt_number` when two attempts share an `exam_date`, not just `exam_date` alone — the previous version could arbitrarily show an earlier attempt's score when two attempts landed on the same day.
- Its paired donut (**Cert Pass Rate**) is the same computation as before, now also showing **average attempts to pass** (`Avg(attempt_number)` over passed attempts only) beneath the legend — a different signal from pass rate: a cert can have a low first-time pass rate but still be cleared quickly on resit.
- **New stat card**: "Not Yet Attempted" — count of active students with zero `InternationalExamAttempt` rows at all. This is the actionable version of what the old competency donut was trying and failing to surface as an average.
- **New: Upcoming Bookings** panel — next 5 scheduled `ExamBooking` rows, linking through to the full Bookings calendar. Brings that Test-Admin-only feature into the Exec Admin's view.
- **New: Pass Rate by Certifying Body** — breakdown bars grouped by `Module.certifying_body` (falls back to `module_code` for modules with no certifying body set), instead of one blended pass-rate number. Answers "which vendor's cert is the problem" rather than just "is the overall rate low."
- Deliberately not added: any trend arrow ("↑ 4% this month") — there's no historical snapshot table in the schema, so a trend would have to be fabricated rather than computed. Flagged as a possible future feature (a `DashboardSnapshot`-style table), not built speculatively.

### ✅ Excel Export (`/admissions/students/export/`)
- Exec Admin only; respects the student list's active filters
- Deliberately excludes `LearningPlatformCredential` and `AccessKey` fields (per SRD requirement 12)

### ✅ Microsoft Entra ID (Azure AD) SSO
- Custom `ITCAOIDCAuthenticationBackend` (`accounts/auth.py`) — the library's default `create_user()` doesn't match our custom `SystemUserManager` signature, so this subclass fixes that and maps `given_name`/`family_name`/`oid` claims onto `SystemUser`
- New users auto-provision as active Data Capturers (lowest privilege) on first login; an Exec Admin upgrades role/campus afterward via `/admin/`
- Public landing page at `/` (`templates/accounts/landing.html`) with a "Sign in with Microsoft" button (`accounts:landing` view) — also doubles as the post-login redirect target, routing each role to its own home page (Exec Admin → dashboard, Trainer → grading, Test Admin → exams, Data Capturer → applications)
- **`.env`'s `AZURE_AD_TENANT_ID` is currently set to `common`** (not the real tenant GUID) to allow personal Microsoft accounts through for testing — this also required setting the App Registration's "Supported account types" to include personal accounts in the Azure Portal. **Revert both before going live**: the real tenant GUID is left commented directly above the line in `.env`, and Azure's "Supported account types" needs to go back to single-tenant-only.
- Local redirect URI registered in Azure must be exactly `http://localhost:8000/oidc/callback/` — Azure rejects `127.0.0.1` for plain-HTTP loopback redirects, so browse via `localhost`, not `127.0.0.1`, when testing sign-in locally

### ✅ Dashboard Access Control
- `/dashboard/` is Exec Admin only; every other role is redirected to their own landing page (see SSO section above) — the nav bar's "Dashboard" link is likewise only rendered for Exec Admins

---

## 6. Outstanding Work

### 🔲 Alumni Management
- Mark student as graduated → create Alumni record
- Alumni list view

### 🔲 Unsuccessful Application Purging
- Automated task/command to purge rejected applications after 1 year retention period

### ✅ Containerized for deployment (Azure Container Apps)
- `Dockerfile`, `.dockerignore`, `entrypoint.sh` (runs `migrate` + `collectstatic` on every container start, then `gunicorn`)
- `requirements.txt` gained `gunicorn` and `whitenoise`
- `itca_sms/settings.py`: `SECURE_PROXY_SSL_HEADER` (Container Apps' ingress terminates HTTPS and proxies over plain HTTP — without this Django thinks every request is insecure), `CSRF_TRUSTED_ORIGINS` (derived from `ALLOWED_HOSTS`), `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` gated on `DEBUG=False`, whitenoise middleware + `STORAGES['staticfiles']` for compressed/hashed static file serving with no separate storage account needed, and `DB_SSL_REQUIRE` env flag (Azure Postgres requires SSL, the local Docker container doesn't have it configured at all)
- `/healthz/` — unauthenticated, no-DB-query endpoint for Container Apps' liveness/readiness probes (`itca_sms/urls.py`)
- **Chose Docker Hub over Azure Container Registry** for the image, to keep the whole stack genuinely free (ACR's cheapest tier isn't free; Docker Hub's free tier — 1 private repo, unlimited public — is more than enough for a single low-traffic Container App image)

### ✅ Deployed to Azure Container Apps — live
- **Live URL**: `https://itca-sms-app.wittybeach-44e8382e.southafricanorth.azurecontainerapps.io` — resource group `itca-sms-rg`, region `southafricanorth`
- **Database**: Azure Database for PostgreSQL Flexible Server, free tier (Burstable B1ms), server `itca-postgres26.postgres.database.azure.com`, database `itca_db`, admin user `itca_sms_admin`. Data migrated from the local Docker container via `pg_dump`/`pg_restore` (`--no-owner --no-privileges`, since the local `itca_user` role doesn't exist on Azure) — row counts verified to match exactly, and `manage.py migrate --plan` confirmed zero schema drift before cutover
- **Image**: `siphelelemsane/itca-sms:latest` on Docker Hub (public repo, free tier). Deployment source on the Container App is set to **Manual** (not continuous deployment) — pushing a new `:latest` tag later requires manually triggering a new revision via "Edit and deploy"
- **Container App config**: Consumption plan, 0.5 CPU / 1Gi memory, ingress on port 8000, health probe `/healthz/`, **min replicas set to 0** for scale-to-zero (this is the setting that actually keeps it inside the free grant — it's a collapsed "Scaling" section easy to miss both during creation and after)
- **Env vars set on the Container App**: `SECRET_KEY` (freshly generated for prod, not reused from local `.env`), `DEBUG=False`, `ALLOWED_HOSTS=itca-sms-app.wittybeach-44e8382e.southafricanorth.azurecontainerapps.io`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT=5432`, `DB_SSL_REQUIRE=True`, `AZURE_AD_TENANT_ID=common` (deliberately kept as `common`, not the real tenant GUID — see below), `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`
- **Azure AD App Registration** redirect URIs now include both `http://localhost:8000/oidc/callback/` (local dev) and `https://itca-sms-app.wittybeach-44e8382e.southafricanorth.azurecontainerapps.io/oidc/callback/` (prod) — verified end-to-end by hitting `/oidc/authenticate/` and confirming the resulting Microsoft authorize URL carries the exact right `client_id`/`redirect_uri`/`tenant`, then by an actual interactive sign-in, which succeeded
- **Deliberate decision, not yet reverted**: `AZURE_AD_TENANT_ID` is staying on `common` in production for now (the client's explicit choice, made knowingly) — personal Microsoft accounts can still sign in and land as Data Capturers. Revert to the real tenant GUID (commented in local `.env`) and restrict the App Registration back to single-tenant-only whenever that's actually wanted

### 🔲 Outstanding from deployment
1. **Rotate the Postgres admin password** — the current one went through chat in plain text during setup. Reset it in the Portal (server → Reset password) and update the `DB_PASSWORD` env var on the Container App to match. Agreed with the client to do this after the initial deployment was confirmed working, not before.
2. Revert `AZURE_AD_TENANT_ID` to the real tenant GUID + restrict single-tenant-only, whenever the client is done wanting personal-account access (see above — currently a deliberate choice, not an oversight)

### 🔲 Testing
- No automated tests written yet — recommend adding as features stabilize, particularly around the approval/capacity logic and assessment average calculations

---

## 7. Known Technical Notes

- **Python 3.14 + Django 6.1** currently in use (upgraded from Django 5.0 due to a `super()` compatibility issue in the admin template engine under Python 3.14).
- **`assessment_type` default** — `default=FORMATIVE_1` on `LocalAssessment.assessment_type` satisfies Django's migration requirement for a non-nullable field on an existing table. Safe since the table was empty at migration time.
- **Windows development environment** — commands documented account for `venv\Scripts\activate`, `mkdir` without `-p`, and PowerShell/CMD path syntax.
- **`requirements.txt`** now exists (it didn't originally) — generated via `pip freeze`, includes `openpyxl` for the Excel export. Keep it updated when adding packages; it'll matter for containerizing the app before Azure deployment.
- **Migrations must stay in sync with `models.py`** — a past session edited models (the `LocalAssessment` redesign, `Student.student_id_code`) without ever running `makemigrations`/`migrate`, which went unnoticed until a full QA pass hit `ProgrammingError: column ... does not exist` on a live query. Always run `python manage.py makemigrations --check --dry-run` after model changes, before assuming a feature works.
- **The `assign_default_modules` signal was documented as built but didn't exist** until this was caught in QA — `admissions/models.py` imported `post_save`/`receiver` but never registered a receiver, so approving an application never auto-assigned default modules or created assessment slots. Now implemented at the bottom of `admissions/models.py`.
- **Azure's loopback redirect URI rule**: for plain-HTTP local redirect URIs, Azure only accepts the literal host `localhost`, not `127.0.0.1`. Always browse to `http://localhost:8000/...` locally, not `127.0.0.1`, to match the registered redirect URI.

---

## 8. Suggested Next Session Priorities

1. Rotate the Postgres admin password (went through chat in plain text during deployment setup — see §6) and update the Container App's `DB_PASSWORD` to match
2. Revert `AZURE_AD_TENANT_ID` to the real tenant GUID and restrict the Azure App Registration back to single-tenant-only, once the client is done wanting personal-account access in production (currently a deliberate choice, not an oversight — see §6)
3. Alumni management (mark student graduated → Alumni record, list view)
4. Unsuccessful application purging (1-year retention job)
5. Automated tests, especially around approval/capacity logic and assessment averages
