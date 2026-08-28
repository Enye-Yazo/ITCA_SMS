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
| **Exec Admin** | Super user. Approves/rejects applications, manages campuses/programs/modules/classes, approves promotions, views all data. |
| **Test Admin** | Records international certification exam attempts and results (CompTIA, Microsoft, etc). |
| **Trainer** | Grades local NQF5 assessments, views student international exam results, requests promotions. |
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
→ deemed Competent overall
   ↓
Trainer requests Promotion
(New → Returning cohort)
   ↓
Exec Admin approves Promotion
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
| `assessments` | StudentModule, LocalAssessment, InternationalExamAttempt, AccessKey, LearningPlatformCredential, Promotion. |
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
- Assessments schema: StudentModule (with `assignment_type`: Default/Elective), LocalAssessment (redesigned for 2 Formative + 1 Summative per module), InternationalExamAttempt, AccessKey, LearningPlatformCredential, Promotion

### ✅ Automated Business Logic (Signals)
- `assign_default_modules` — fires on `Student` creation, snapshots current `ProgramModule` defaults into `StudentModule` records
- `create_local_assessment_slots` — fires on `StudentModule` creation, creates the 3 empty assessment records (PFA01, PFA02, PSA)

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

### ✅ Settings Page (`/academics/settings/`)
- Tabbed interface: Campuses, Programs, Modules (+ Program-Module linking), Classes
- Add/edit forms for each entity
- Exec Admin-only access via `@exec_only` decorator

### ✅ Design System — "Liquid Glass"
- Full-bleed backdrop image (`static/images/backdrops/turqoise.jpg`) behind every page, with a navy gradient overlay for text contrast — replaces the old flat `#0F1B2D` fill so `backdrop-filter: blur()` panels actually have something to distort
- Shared glass surface classes: `.glass` (panels), `.glass-soft` (nested/smaller elements), `.glass-nav` (top nav bar), `.modal-scrim` (dialog backdrop) — all in `static/css/source.css`, compiled via `npm run tailwind:build`
- `.stat-card`, `.dash-table`, `.filter-pill` all carry the same blur/saturate treatment
- Extra backdrop assets available in `static/images/backdrops/` (`cloud.png`/`cloud.jpg` used as the landing page hero illustration) — swap the body background image there if a different backdrop is wanted
- ITCA logo integrated into navbar

### ✅ Trainer Grading Interface (`/assessments/grading/`)
- Table view: Student ID, Name, Cohort, Module, PFA01/PFA02/PSA columns, scoped to the logged-in trainer's own students only
- Click a row → popup tile for entering formative marks (with remediation, enforced server-side to require an original mark below 95%) or summative competency
- Popup only closes on a confirmed successful save from the server
- IDOR-protected: a trainer cannot grade another trainer's student via a guessed URL

### ✅ Student List and Detail View (`/admissions/students/`)
- Filters: Campus, Program, Cohort, Trainer (Exec Admin only); search by Student ID
- Detail view: profile, modules with local assessment marks, enrollment history, promotion history
- Exec Admin sees every student; Trainers see only their own (IDOR-protected)

### ✅ Test Admin Interface (`/assessments/exams/`)
- Records international exam attempts, restricted to modules with `is_international_assessment=True`
- `attempt_number` computed server-side (never trusted from the client)
- Filterable history by module and Pass/Fail

### ✅ Promotion Workflow (`/assessments/promotions/`)
- Trainer requests promotion from an active New-cohort enrollment to a Returning class in the same program/campus
- Exec Admin approves (atomically: marks old enrollment `Promoted`, creates new `Active` enrollment in the target class) or rejects
- Guards: one pending request per enrollment, can't re-review an already-decided request

### ✅ Dashboard Enhancements
- Second donut chart: Summative competency (Competent ≥94% formative average vs Not Yet Competent), excluding ungraded students from the denominator
- `Student.formative_average` / `Student.is_competent` model properties wired into both dashboard stats and the export

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

### 🔲 Azure Deployment
- Containerize the Django app (currently only PostgreSQL is in Docker)
- Azure Database for PostgreSQL setup
- Azure App Service or Container Apps deployment
- Environment variable / secrets management (Azure Key Vault likely)
- Static file serving strategy (Azure Blob Storage or WhiteNoise)

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

1. Revert `.env`'s `AZURE_AD_TENANT_ID` to the real tenant GUID (commented above the line) and restrict the Azure App Registration back to single-tenant-only once personal-account testing is done
2. Alumni management (mark student graduated → Alumni record, list view)
3. Unsuccessful application purging (1-year retention job)
4. Automated tests, especially around approval/capacity logic and assessment averages
5. Azure deployment: containerize the app, Azure Database for PostgreSQL, App Service/Container Apps, secrets management, static file serving strategy
