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
| **Test Admin** | Records international certification exam attempts and results (CompTIA, Microsoft, etc). Also creates student email accounts and manages external vendor learning-platform/lab credentials (Platform Management). |
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
Signal fires: LocalAssessment slot created
per NQF5 (local-assessment) module, empty
   ↓
Trainer rates each module Competent /
Not Yet Competent, with an optional comment
   ↓
Every assigned NQF5 module rated Competent
→ deemed Competent overall
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
- **Local (NQF5) assessment structure — simplified per client instruction**: each NQF5 module (`Module.is_local_assessment=True`) gets exactly one rating — Competent or Not Yet Competent, with an optional trainer comment — auto-created (empty) the moment a student is assigned that module. The earlier 2-Formative (95% pass mark, one remediation attempt) + 1-Summative design, and the numeric formative-average competency metric it produced, has been removed entirely (see "NQF5 Simplification" below); there are no marks or percentages anywhere in local assessment any more, only the two-value rating.
- **Overall student competency** — a student is Competent once **every** NQF5 module they're assigned is rated Competent (all-or-nothing, `Student.is_competent`). `Student.is_evaluated` is true once at least one assigned NQF5 module has any rating at all (used as the "has grading started" denominator in Reports/trainer-roster pass rates).
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
- Full admissions schema: Applicant (with auto-generated `application_reference` and a `referral_source` dropdown), StudentContact, Student (with auto-generated `student_id_code`), Alumni
- Assessments schema: StudentModule (with `assignment_type`: Default/Elective), LocalAssessment (one Competent/Not Yet Competent rating + comment per NQF5 StudentModule — see "NQF5 Simplification"), InternationalExamAttempt, ExamBooking, AccessKey, LearningPlatformCredential

### ✅ Automated Business Logic (Signals)
- `assign_default_modules` — fires on `Student` creation, snapshots current `ProgramModule` defaults into `StudentModule` records
- `create_local_assessment_slot` — fires on `StudentModule` creation, creates the single empty NQF5 rating slot **only for modules flagged `is_local_assessment=True`** — international-exam-only modules never get one (this filter was missing before the NQF5 Simplification fix, which was the root cause of international modules wrongly appearing on the Grading page)
- `auto_promote_on_full_nqf5_pass` — fires on every `LocalAssessment` save, promotes a student from their active New-cohort enrollment to a Returning class the moment `Student.is_competent` goes true (see "Automatic Promotion" below)
- `backfill_default_module_for_active_students` (`academics/models.py`) — fires on `ProgramModule` creation with `is_default=True`, and **deliberately overrides the "default assignment is a snapshot" rule for this one action** (client request): it retroactively assigns the module to every currently actively-enrolled student in that program who doesn't already have it, not just future ones. Root case that prompted this: Cyber Security's MCT06/07/08/09 were linked as defaults at various points, but students admitted before each link existed never got them, so a trainer's Grading page was missing NQF5 columns for students who should have had them. A one-time catch-up loop (same logic, run manually once) closed the gap for every pre-existing default link across both programs — 20 `StudentModule` rows backfilled in total (6 for the one CYB student at the time, 14 across two SFTW students).

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
- **Step 1 now captures how the applicant heard about ITCA** (`referral_source`, labeled "Referral") — the field and its options already existed on `Applicant` and in `PersonalDetailsForm.Meta.fields`, but the dropdown was never actually rendered in `step_1_personal.html`, so it sat empty on every application until this was caught. Options were also replaced with the client's exact list: Website, Word Of Mouth, Career Expo, School Outreach, Social Media (previously Word of Mouth/Facebook/Exhibition/Find a Friend/Website) — migration `admissions.0006_alter_applicant_referral_source` also normalizes existing `'Word of Mouth'` rows to the new choice's exact casing (`'Word Of Mouth'`). **Required** at the form level (`PersonalDetailsForm` declares it explicitly with `required=True`) — the underlying model field stays `blank=True`/`null=True` since historical-onboarding backfills and other non-form creation paths don't need to supply one.
- **Draft vs Pending, fixed**: `application_step`'s step 1 save used to set `application_status` straight to `Pending` — meaning a Data Capturer's in-progress, not-yet-submitted application already looked identical to a genuinely submitted one awaiting Exec Admin review, on both the Exec Admin's applications list and the dashboard's "Pending Applications" count. `application_submit` (the real "Submit for approval" action at step 5) never actually changed the status at all — its own docstring admitted as much ("Changes status from Pending to Pending (already set)"). Added a `Draft` status: step 1 now sets `Draft`, and `application_submit` is what actually transitions `Draft → Pending`. Historical onboarding is unaffected — it goes `Draft → Approved` directly via `onboard_confirm`, skipping Pending entirely, same as before.
- **Waitlist workflow removed** — `Applicant.ApplicationStatus.WAITLISTED` was a dead choice: nothing anywhere ever set it (confirmed zero rows before removal), so it was a UI badge case with no code path that could ever trigger it. Removed from the model and `application_list.html`'s badge styling, replaced by a `Draft` badge case there instead.
- Also cleaned up while touching this model: `Applicant` had `date_applied`/`application_status`/`status_date` declared **twice** (identical duplicate field definitions, harmless to Django but confusing) — removed the second copy.

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
- The Modules and Program-Module Links tiles lists are vertically scrollable (`max-h-[28rem] overflow-y-auto`) rather than letting the tile list expand and push the rest of the page down — there are 20+ modules once both NQF5 and international-cert ones are counted.
- **Bug fixed**: adding/editing/deleting a Campus, Program, Module, Program-Module link, or Class used to redirect back to `academics:settings` with no `?tab=` query param, dropping the Exec Admin back on the default Campuses tab instead of wherever they'd actually been working — not an architecture limitation, just every one of those views' redirects missing the query param that `class_delete` (alone) already got right. Every add/edit/delete view for all five entity types now redirects with the correct `?tab=` (Program-Module link actions specifically redirect to `?tab=modules`, since that section lives inside the Modules tab, not a separate one — `program_module_add`'s error-redisplay path had also been passing a nonexistent `active_tab='program_modules'`, silently leaving no tab visually marked active on a validation error; fixed to `'modules'` too).

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

### ✅ Dark mode (toggle-able) + contrast fix — v2, after client feedback on v1
- **Contrast fix, v2**: v1 used `color-mix()` at 68% effective strength, which still read as "grey" per client feedback ("consider making it darker") — replaced with flat, precomputed colours per theme (`#3f4555` light / `#c5c5c7` dark, ~80% effective strength, ~7:1 contrast) for the same merged `text-itca-navy/20`–`/60` selector, no `color-mix()` and no browser-support fallback to reason about. Still un-layered CSS (beats Tailwind's own layered utilities regardless of source order), still zero template edits needed despite ~180 usages app-wide, including every field label in the Data Capturer's application form.
- **Dark palette, v2**: v1's dark backgrounds were navy/blue-tinted (`#0b1220`, `#131b2e`, `#161f34`) — per client feedback ("the navy doesn't improve readability"), replaced with neutral dark grays (`#121212`/`#1a1a1d`/`#202024`/`#2a2a2f`) with a near-white, non-blue text colour (`#f2f2f4`). Status badge colour pairs (blue/green/amber/red/purple) keep their hue, just retuned to sit on a neutral backdrop instead of a blue one.
- **Toggle-able dark theme**, three-state: an explicit choice (the sun/moon button in `base.html`'s nav, top-right on `accounts/landing.html`) sets `data-theme="dark"`/`"light"` on `<html>` and always wins; with no explicit choice, `prefers-color-scheme` (the OS/browser setting) decides. The choice persists in `localStorage` (`itca-theme`) and is re-applied by an inline pre-paint `<script>` at the very top of `<head>` (duplicated into `landing.html`'s own `<head>` since that page deliberately doesn't extend `base.html`) — this runs before any CSS paints, so there's no flash of the wrong theme on load.
- Implemented entirely as CSS custom-property overrides in `source.css`, guarded by `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` and `:root[data-theme="dark"]` (both blocks kept in sync) — every existing color token (`--color-itca-navy`, `-bg`, `-surface`, `-border`, `-muted`, every `-light`/`-dark` status pair) gets a dark-mode value. Two new internal-only tokens (`--color-card-bg`, `--color-hover-bg`) replaced hardcoded `#ffffff`/`#f8fafc` in `.surface`, `.stat-card`, `.surface-nav`, inputs, `.dash-table`, `.filter-pill`, `.btn-secondary`, so those flip too. `.badge-purple` (previously the one hardcoded-hex badge instead of a token pair) now uses new `--color-itca-purple-light`/`-dark` tokens, for the same reason. The vendored flatpickr calendar also gets a small dark override (it hardcodes a white popup otherwise).
- Because nearly every template already routed its colors through these named tokens rather than arbitrary Tailwind grays, this was primarily a CSS-token exercise, not a per-template rewrite — the one real per-template fix was `accounts/landing.html`'s two hardcoded panel backgrounds (a plain white form panel, a light-blue gradient illustration panel), given their own small `<style>` block since that page has no shared stylesheet hook into `source.css`'s component classes for page-specific backgrounds.
- **Not yet dark-mode-tuned** (would need a follow-up pass if it turns out to matter): the dashboard's SVG donut charts and any other inline SVG using literal hex fills rather than CSS custom properties — not touched, since none were found wired through the existing token system the way everything else was.
- **Also rebuilt with the v6 hero + tab-strip layout**: Settings (tabs now sit inside the gradient hero), Grading (real "NQF5 Assessments / Int. Certifications / Attendance" tab strip — Int. Certifications is a new read-only view at `assessments:trainer_intcert`, Attendance links to the register), Exam Results (hero + "Exam Results / Bookings" tab strip), Bookings (now has an actual month calendar grid with prev/next navigation, plus the upcoming list)
- **Not yet rebuilt to the mockup's exact visual treatment** (functionally complete, just plainer): Exam Results is still a flat filterable table rather than the mockup's expandable per-student card list — reworking that would mean regrouping the underlying query by student, a bigger change than a style pass

### ✅ New backend features added to support Redesign v6 screens that had no prior model/view
- **Attendance** (`academics.AttendanceRecord`, `/attendance/`, Trainer-only) — one row per student per day (Present/Late/Absent + time-in + notes) for the trainer's own active class; a record is auto-created defaulting to Present the first time a date is opened so the trainer only edits exceptions. MTD attendance rate computed per student per month.
- **Trainer roster** (`accounts:trainer_list`, `/trainers/`, Exec Admin-only) — card grid of every Trainer with active student count and NQF5 pass rate, computed live from `Student.is_evaluated`/`is_competent` (no new stats model needed)
- **Reports** (`dashboard:reports`, `/dashboard/reports/`, Exec Admin-only) — NQF5 pass rate by program and certification pass rate by module, aggregated live from existing `LocalAssessment`/`InternationalExamAttempt` data
- **Exam Bookings** (`assessments.ExamBooking`, `/assessments/bookings/`, Test Admin-only) — schedules a future exam sitting (date/time) against a `StudentModule`, distinct from `InternationalExamAttempt` which records the actual result once sat; a booking can optionally link forward to the attempt that resulted from it
- **User invite** (`accounts:user_invite`, `/accounts/users/invite/`) — lets an Exec Admin pre-create a `SystemUser` (unusable password, same as Entra auto-provisioning) ahead of that person's first Microsoft sign-in, rather than only being able to edit a role after their first login
- Both migrations (`academics.0004_attendancerecord`, `assessments.0004_exambooking`) are **applied to the live local DB** — verified via `showmigrations`, `makemigrations --check` (no drift), and a direct `\d` on both tables in `psql` confirming columns/FKs match the models exactly. Every restyled/new view was also smoke-tested with Django's test `Client` against real DB users (exec admin, test admin, a temporary trainer created and rolled back) — all returned 200.
- Exam Results (`assessments:exam_attempt_list`) was reworked from a flat table into the mockup's expandable per-student card list — `exam_attempt_list` view now also builds `grouped_attempts` (attempts bucketed by student, with passed/failed counts) alongside the original flat `attempts` queryset so both the card list and any future flat view stay in sync.
- **Schema documentation**: a full ER diagram + per-table column/FK reference, reverse-engineered directly from Postgres's `information_schema` (not copied from `models.py`), was published as an artifact — see "ITCA Schema Atlas" in this session's artifacts. Covers all 19 domain tables across the four apps, with the two new tables called out.

### ✅ Trainer Grading Interface (`/assessments/grading/`) — NQF5 competency matrix
- **Matrix layout, not one row per module**: one row per student, one horizontally-scrollable column per NQF5 module assigned to any of the trainer's students — replaces the earlier one-row-per-module-per-student PFA01/PFA02/PSA table, which duplicated each student's name down the page once per module.
- The module column set is derived from the trainer's own students' actual NQF5 `StudentModule` assignments (`module__is_local_assessment=True`), not hardcoded — it naturally reflects whichever program(s) the trainer's students are in.
- Click a cell → a themed modal opens (Competent / Not Yet Competent radio choice + an optional comment textarea); on save the cell updates in place to show just **C** or **NYC** (badge-green/badge-red), no page reload. Modal only closes on a confirmed successful save from the server.
- IDOR-protected: a trainer cannot grade another trainer's student via a guessed URL, and the endpoint rejects grading a module that isn't flagged `is_local_assessment`.

### ✅ Student List and Detail View (`/admissions/students/`) — Exec Admin + Test Admin
- **Security fix**: this used to also be reachable by Trainers (their own students, IDOR-protected) via a "Students" nav link — which unintentionally exposed full demographic details (ID number, date of birth, address, disability status, POPIA consent, etc.) that Trainers have no business reason to see. `student_list` and `student_detail` no longer permit Trainers at all, and the "Students" nav link no longer renders for them — a Trainer's only view of their own students is "My Students" (`assessments:grading_index`), which shows names, IDs, and NQF5 ratings, nothing demographic.
- **Test Admin was then explicitly granted access** (client instruction) — they need to look a student up before creating their external vendor learning-platform profiles (Microsoft Learn, CompTIA, etc. — see Platform Management). Test Admin sees the same read info Exec Admin does (including demographics — the exposure this was originally locked down for was Trainers seeing it without a reason, not the info itself being sensitive to any admin role), but not the "Delete student" or "+ Add module" controls, which stay Exec Admin-only (gated in the template, not just by URL).
- Filters: Campus, Program, Cohort, Trainer; search by Student ID
- Detail view: profile, an **"Academic Standing"** section (renamed from "Modules & NQF5 Assessments" everywhere it appeared) — **showing each module's full name, not its code** (a short muted code line sits underneath for reference) — with each NQF5 module's Competent/Not Yet Competent rating, enrollment history (a `Promoted` row followed by a new `Active` row in this same table is a student's promotion history — see "Student Lifecycle" below)
- **Academic Standing is Exec Admin only** — Test Admin (who can view this page to set up vendor platform accounts) has no reason to see academic progress, so they get Demographic Details and Enrollment History only; the whole section (including its "+ Add module" control) is gated behind `{% if request.user.is_exec_admin %}`.
- **Add module** (Exec Admin only) — a small modal lets an Exec Admin add an extra module to a student's package directly from their profile (e.g. a Software Development student picking up Security+ from Cyber Security). Always added as an `Elective` `StudentModule` — a manual, one-off addition, not a program default.
- **Delete student** (Exec Admin only) — a themed-confirm-gated button on the profile header permanently deletes the student and everything that hangs off them (enrollment history, modules, local assessments, exam attempts, platform credentials, their `Applicant`/`StudentContact` record). `admissions.views._delete_student_and_records` handles the deletion in the order the schema's `PROTECT` relations require (Enrollment/StudentModule/Alumni/LearningPlatformCredential before the Student, the Student before its Applicant) — reused by both this view and any future bulk-cleanup scripts.
- The Student Email edit control (profile header) is available to both Exec Admin and Test Admin, matching who `admissions:student_set_email` already permitted.

### ✅ Test Admin Interface (`/assessments/exams/`)
- Records international exam attempts, restricted to modules with `is_international_assessment=True`
- `attempt_number` computed server-side (never trusted from the client)
- Filterable history by module and Pass/Fail
- **Pass/Fail is computed, not picked**: the recording form takes a `pass_threshold` (minimum score to pass — differs per certification, entered per attempt) alongside the score; `InternationalExamAttempt.exam_result` is set server-side as `score >= pass_threshold`, never chosen from a dropdown. Pre-existing rows (recorded before this field existed) were backfilled to a threshold of 700, matching what used to be a hardcoded assumption in the UI — their already-recorded results were left untouched.

### ✅ Modern date pickers (flatpickr, app-wide)
- Every native `<input type="date">` (browser-default, locale-dependent picker) has been replaced with [flatpickr](https://flatpickr.js.org), vendored locally at `static/vendor/flatpickr/` (not loaded from a CDN) and retinted from its "airbnb" theme's pink/red to ITCA blue via an override block at the bottom of `static/css/source.css`.
- `templates/base.html` loads flatpickr once, app-wide, and auto-initialises it on **any** input carrying the `js-datepicker` class — so any current or future date field opts in just by adding that class to its widget, no per-page JS needed.
- All dates are entered/displayed as **dd/mm/yyyy**, parsed via each field's `input_formats=['%d/%m/%Y']` (Django's default `en-us` locale formats don't include dd/mm/yyyy, so this must be set explicitly per field — it doesn't come for free from `LANGUAGE_CODE`).
- Converted: the Data Capturer's application form (`admissions.PersonalDetailsForm.date_of_birth`), the historical-onboarding "Enrolment start date" field, the Test Admin's Exam Results (`InternationalExamAttemptForm.exam_date`) and Bookings (`ExamBookingForm.exam_date`) forms, and the Trainer's Attendance register date selector (`templates/academics/attendance.html`) — every date field parsed manually from a plain HTML input rather than a Django form field (the onboarding start date and the attendance date) was updated from `date.fromisoformat()` to `datetime.strptime(..., '%d/%m/%Y')`, since a native `<input type="date">` always submits ISO regardless of display locale but a text input driven by flatpickr submits whatever `dateFormat` it's configured with.
- The attendance date field auto-submits its form on pick (`onChange` calls `form.submit()`), replacing the native input's `onchange` — it's excluded from base.html's generic `.js-datepicker` auto-init specifically so it can carry that extra callback, and is `readonly` so free-typing can't produce a value the auto-submit assumes is already valid.
- No native `type="date"` input remains anywhere in the app.

### ✅ NQF5 Simplification — bug fix + model redesign
- **Bug fixed**: the Trainer's Grading page was showing international-certification modules (e.g. A+, Network+, Security+) instead of the real NQF5 modules, and the actual NQF5 (MCT0x) modules never appeared at all. Root cause was two-fold: (1) `grading_index` never filtered `StudentModule` by `module__is_local_assessment=True`, so it showed every module a student had, local or international; (2) the `LocalAssessment`-creation signal fired unconditionally for *every* `StudentModule`, including international-only ones, so those bogus modules actually had (empty) local-assessment rows to display. Both are fixed — the signal now only fires when `module.is_local_assessment` is true, and the Grading view filters on the same flag as defense in depth.
- **Business rule simplified, per explicit client instruction**: the old 2-Formative (95% pass mark, one remediation attempt allowed) + 1-Summative structure is gone. `LocalAssessment` is now a single row per `StudentModule` (a `OneToOneField`, not a `ForeignKey`) holding one `competency` value (`Competent` / `Not Yet Competent`, or blank if ungraded) and an optional `comment` — no marks, no percentages, no remediation anywhere in local assessment any more.
- **Grading page rebuilt as a competency matrix** (see "Trainer Grading Interface" above) — one row per student, one column per NQF5 module, instead of one row per student-per-module (which duplicated each student's name down the page once per module, the exact complaint that prompted this).
- **Migration note**: `assessments.0009_alter_localassessment_options_and_more` clears the `local_assessments` table before applying the schema change, since the old 3-rows-per-module structure would otherwise violate the new `OneToOneField`'s unique constraint on `student_module_id`. Verified safe first — every existing row had `mark IS NULL` and `competent IS NULL` (checked via raw SQL against the live table before writing the migration), i.e. nothing had actually been graded yet under the old structure.
- `Student.formative_average` and the old `Student.all_nqf5_passed` are both gone, replaced by `Student.is_competent` (all assigned NQF5 modules rated Competent — used both as the "is this student competent" flag and the automatic-promotion trigger) and a new `Student.is_evaluated` (at least one assigned NQF5 module has any rating at all — the "has grading started" denominator Reports/trainer-roster pass rates use).

### ✅ Themed confirm dialogs — replaced `window.confirm()` app-wide
- Every "Delete"/"Reject"/"Remove" action previously used the browser's native `confirm()` popup, which looks inconsistent with the rest of the app and can't be restyled. All ~10 call sites (Settings' Campus/Program/Module/Class delete and Program-Module unlink, Users list delete, application Reject, and Platform Management's table/column/row delete) now call a shared `itcaConfirm(message, form)` helper defined once in `templates/base.html`, which opens a themed modal (same rounded-surface/modal-scrim look as every other dialog in the app) with Cancel/Confirm buttons and submits the given form only once Confirm is clicked.
- `form` is normally `this.form` (the button's own enclosing form); the one exception is the Users list, where the delete button lives outside its form via the `form="..."` attribute, so it passes that form's id as a string instead — `itcaConfirm` accepts either.

### ✅ Platform Management (`/assessments/platform/`, Test Admin only)
- New third tab alongside Exam Results / Bookings in the Test Admin portal — Test Admin owns provisioning of student email accounts and external vendor learning-platform/lab credentials, not Exec Admin.
- Two sections, **Access Credentials** and **Labs**, each holding a set of vendor tables (`PlatformTable`) seeded on migration with the four the client asked for: Access Credentials → Microsoft (Password, MCID) and CompTIA (Password, CompTIA ID); Labs → Microsoft (AZ-900, AZ-400) and CompTIA (SC-100, Security+).
- Deliberately an EAV-style schema (`PlatformTable` → `PlatformColumn` → `PlatformRow` → `PlatformRowValue`) rather than one fixed model per vendor, since the Test Admin can add/rename/delete whole tables and columns at runtime — e.g. onboarding a new certifying body — without a migration each time. Name, Program Code and Student Email are never duplicated into this schema; every row just links to a `Student` and reads those live off it.
- Every custom column value is click-to-edit inline (AJAX, same pattern as the Grading page's popup save) — no separate edit form/page. Columns typed `Text` or `Password` (password values render masked until clicked into edit).
- If a row's student has no `student_email` yet, an inline "+ Create email" control posts straight to `admissions:student_set_email` (now permitted for Test Admin as well as Exec Admin, with a `from_platform=1` flag so the redirect lands back on Platform Management instead of the student detail page).
- Full add/delete for tables, columns, and rows (students), all Test-Admin-only and CSRF-protected POST actions.

### ✅ Student Lifecycle — New → Returning → Alumni (3rd redesign of this flow)
The lifecycle has been through three designs this engagement: manual Trainer-requests/Exec-Admin-approves Promotion → a single NQF5-completion-triggered auto-promotion (New straight to Returning) → the current, final split below. The trigger changed because of a business fact that only came up partway through: **NQF5 modules are only assessed in a student's *second* year (Returning) — their first year (New) is Int. Cert-focused**, which made "NQF5 completion promotes New → Returning" nonsensical (a New student can never satisfy it, since nobody grades their NQF5 yet). The two transitions are now driven by two different, independent mechanisms:

**New → Returning: purely time-based, not tied to any assessment result.**
- `academics.AcademicCalendar` is a singleton (`AcademicCalendar.load()`, always `pk=1`) holding `year_start`/`year_end` — Exec Admin-configurable in Settings' new **Academic Calendar** tab, defaulting to 1 Feb – 15 Dec.
- `academics.models.run_end_of_year_promotion()` promotes every actively-enrolled New-cohort student to the matching Returning class (same program+campus, active, regardless of academic_year label — see the function's docstring for why the label isn't matched) the moment `today >= year_end`, exactly once per cycle (`AcademicCalendar.last_promoted_year` guards re-running it) — and correctly leaves *only* the students whose program/campus has no active Returning class yet unpromoted, re-checking them (without re-marking the whole cycle done) on every subsequent call, rather than a single missing class silently blocking the promotion tracking forever.
- There's no Celery/cron in this app, so this is called lazily at the top of the Exec Admin's own dashboard view on every load (cheap — no-ops instantly once already run for the year) — a stopgap, not the intended long-term mechanism. `python manage.py promote_new_cohort_students` runs the same check, for a real scheduled trigger (an Azure Container Apps Job, or host cron calling into the container) to use instead later.

**Returning → Alumni: competency-based (NQF5 only) — this is the old auto-promotion signal, retargeted.**
- `assessments.models.auto_graduate_on_full_nqf5_pass` (a `post_save` signal on `LocalAssessment`, same trigger point as the old auto-promotion signal) checks `Student.is_competent` after every rating is saved. Only fires for a student whose **active enrollment is Returning-cohort** — a New-cohort student passing NQF5 can't happen any more anyway, now that Grading only shows Returning students (see below), but the check is explicit regardless.
- On trigger: creates an `Alumni` record (`program`, `campus`, `graduation_date` = today) and marks the active enrollment `Completed`. Idempotent via `get_or_create` on `Alumni.student` (OneToOne) — a student can only graduate once.
- **Passing international certifications is explicitly NOT required to graduate** — a student can keep resitting a failed cert indefinitely, in their Returning year and beyond; only NQF5 completion gates graduation. This was a specific point of clarification from the client, not an oversight.
- `admissions/views.py`'s `student_detail` view and template show no separate "Promotion History" table — a `Promoted` row followed by a new `Active` row in the Enrollment History table on that page *is* that student's New→Returning promotion history.
- Verified end-to-end in rolled-back transactions: a New-cohort student rated Competent on every NQF5 module did *not* graduate (correctly — their active enrollment is New, not Returning); a Returning-cohort student rated the same way *did* graduate (Alumni record created, enrollment marked Completed); `run_end_of_year_promotion()` promoted 20 New-cohort students to Returning in one call and correctly no-op'd on a second call.

### ✅ Grading — NQF5 restricted to Returning-cohort students
- The Grading matrix (`assessments:grading_index`) now only shows a trainer's **Returning**-cohort students — a New-cohort student's NQF5 modules are still assigned underneath (ready the moment they become Returning, per the default-module-assignment signal), just not shown or gradable yet, matching "NQF5 only comes into effect in year 2."
- Enforced in both places: the matrix's own query (`student__enrollments__status=Active, student__enrollments__class_group__cohort=Returning`) and `grade_update` itself (rejects grading a StudentModule whose student's active enrollment isn't Returning) — so a Trainer can't grade a New-cohort student's NQF5 via a guessed `student_module_id` either.

### ✅ Alumni page (`/admissions/alumni/`, Exec Admin only) — replaces "Trainers" in the nav
- **Replaced the "Trainers" nav link and roster page with "Alumni"** — computing trainer performance metrics isn't needed right now, per client instruction. `accounts:trainer_list` (the view/URL/template) is left in place but unlinked from the nav, in case it's wanted back later, rather than deleted outright.
- Lists every `Alumni` record (populated automatically by the graduation signal above), each always carrying a **Graduated** badge, plus one badge per international certification the student has *passed* (`InternationalExamAttempt.exam_result=True`, deduplicated by module, shown by name not code) — purely informational, since passing Int Certs was never a graduation requirement.
- **Given a full v6 treatment** (hero banner, stat cards, filters — it started as a bare list): filterable by Campus, Program, graduation Year, and a name/Student ID search. Three stat cards — Total Alumni (respects the active filters), Graduated This Year, and Avg. Certs Passed per graduate.
- **Grouped into two sections, per client request**: "NQF5 + International Certified" (graduated *and* passed at least one Int Cert) and "NQF5 Only" (graduated on NQF5 alone, no Int Cert passed) — makes the achievement split visible at a glance instead of one flat list. A student's row moves between sections automatically as their `InternationalExamAttempt` history changes; nothing needs to explicitly reassign them.
- ~~Each row also shows how long that student actually took, start-to-finish~~ — **removed per client request**, along with the graduation date itself, right after being added. Neither `duration_label` nor the enrollment-lookup that computed it are still in `alumni_list`'s view code.

### ✅ Dashboard Redesign — International Exams elevated, NQF5 removed
- **The NQF5 Assessments table and its Summative-competency donut were removed from the dashboard entirely** — pairing a formative-average donut against a mixed NQF5/international table never made clean sense as a metric, per client feedback. `Student.is_competent` is unaffected everywhere else (Reports page, graduation signal) — this was a dashboard-only removal.

### ✅ Dashboard Redesign — International Exams elevated, NQF5 removed
- **The NQF5 Assessments table and its Summative-competency donut were removed from the dashboard entirely** — pairing a formative-average donut against a mixed NQF5/international table never made clean sense as a metric, per client feedback. `Student.is_competent` is unaffected everywhere else (Reports page, auto-promotion) — this was a dashboard-only removal.
- **International Exam Attempts elevated** into that table's former primary position (2/3 width) — now shows each student's most recent attempt (module, score, Passed/Failed), not just a raw percentage. The "most recent" lookup breaks ties on `attempt_number` when two attempts share an `exam_date`, not just `exam_date` alone — the previous version could arbitrarily show an earlier attempt's score when two attempts landed on the same day.
- Its paired donut (**Cert Pass Rate**) is the same computation as before, now also showing **average attempts to pass** (`Avg(attempt_number)` over passed attempts only) beneath the legend — a different signal from pass rate: a cert can have a low first-time pass rate but still be cleared quickly on resit.
- ~~**New stat card**: "Not Yet Attempted"~~ — **removed again per later client feedback** (kept the tile grid at a clean 5 across, `lg:grid-cols-5`). The underlying computation was deleted too, not just the tile — nothing else referenced it.
- **International Exams table and Upcoming Bookings both scroll vertically** now (`max-h-96`/`max-h-80 overflow-y-auto`) instead of growing the page — Upcoming Bookings' query cap was also raised from 5 to 20 to make the scroll meaningful. The International Exams table's `{{ stats.total_attempts }} attempt(s)` badge next to the heading was removed per client feedback. Clicking a student's name there opens a modal listing their **full** international exam attempt history (every module, every attempt) — the table row itself still only ever shows their latest attempt (one row per student, never one per attempt), with the full history embedded per-row via `{% json_script %}` and read by the modal's JS on click, rather than a new endpoint.
- **New: Upcoming Bookings** panel — next 5 scheduled `ExamBooking` rows, linking through to the full Bookings calendar. Brings that Test-Admin-only feature into the Exec Admin's view.
- ~~**Pass Rate by Certifying Body**~~ — **replaced by "Modules Needing Attention"** (went through two iterations per client feedback):
  - v1 flagged any module with at least one failed *attempt*, ranked by attempt-level pass %. Client feedback: too loose a bar, and attempt-counting is misleading — a module where every student eventually passes on resit still looked bad if failed first attempts were common.
  - **v2 (current)**: flags a module only when **more than 40% of the *students* who've actually sat it have never passed it** (per-student, not per-attempt — a student who failed once then passed on resit counts as a pass). Visual style changed too, from a ranked progress-bar list to a short alert-card list (big red percentage + "X of Y students haven't passed yet") — with a strict >40% threshold this list is usually 0-3 items, and "how severe is this" reads better than "how does this compare to the others" for that few items.
- Also removed: the donut's "⚠ Below Target" alert comparing the pass rate to a hardcoded 85% "institutional target" that was never a real, configured figure — per client feedback ("hard coded value that serves no purpose"). The card now always shows the plain "Based on N attempts" line instead.
- **Module code → module name**: the International Exams table, its per-student exam-history modal, the Test Admin's Exam Results table (+ its module filter dropdown), and the Trainer's read-only Int. Certifications view all used to show a module's short code (e.g. `220-1201`) where a human is reading it — all switched to the full `module_name` (e.g. "A+ Core 1"). Booking-related displays were left as codes (not part of this request).
- ~~**Upcoming Bookings**~~ — **replaced by "Pass Rate by Campus"**. Bug found: its "View all bookings →" link pointed at `assessments:booking_list`, which is Test-Admin-only — an Exec Admin clicking it just bounced back to the dashboard they were already on. Rather than loosen that page's permission (it stays Test-Admin-only, correctly — verified an Exec Admin still can't reach it directly), the tile itself was replaced. The new one compares international exam pass rate per campus (same international-only scope as the "Cert Pass Rate" donut, deliberately not blended with NQF5), plus a one-line summary computed server-side (not template arithmetic).
  - **Rendered as a sorted, scrollable bar list, not a fixed side-by-side grid** — the first version used a CSS grid with one column per campus, which reads fine with exactly 2 campuses but breaks the moment a 3rd, 4th, etc. is added (client feedback: "comparing campuses doesn't seem scalable long term"). The comparison summary line also scales past 2 — two campuses gets "X leads Y by N points" / "even"; three or more gets "Highest: X (P%) · Lowest: Y (P%)" instead.
- ~~**"New Registrations by Month"**~~ — added, then **removed again per client request** shortly after. The underlying point still stands (see the correction above this line) even though this particular panel didn't stick.
- ~~Deliberately not added: any trend arrow ("↑ 4% this month") — there's no historical snapshot table in the schema, so a trend would have to be fabricated rather than computed.~~ **This was too broad a conclusion** — a point-in-time comparison (e.g. "active students vs. last month") genuinely does need a snapshot table, but a *rate-over-time* trend doesn't, whenever the underlying records already carry a real date: "New Registrations by Month" (below) is exactly that, computed straight from `Enrollment.start_date` with no snapshot involved. Still true for anything that needs "what was true as of a past date" rather than "how many things happened in each past period."

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

### 🔲 Unsuccessful Application Purging
- Automated task/command to purge rejected applications after 1 year retention period

### ✅ Performance pass — N+1 queries fixed, per client report ("the system feels slow")
Measured actual per-page query counts with `django.db.connection.queries` (`DEBUG=True`, real logged-in requests via the test `Client`) against live data before guessing at fixes. Every real bottleneck found was a classic N+1 — a query issued once per row in a Python loop instead of once for the whole batch:
- **Reports page: 200 queries → 13.** `Student.is_evaluated`/`.is_competent` (admissions/models.py) each used to run their own fresh `LocalAssessment`/`StudentModule` query *every time they were called*, and both are called once per student in this view. Rewrote both properties to read through the `student_modules` related manager instead of issuing a filtered query — this is what lets a queryset benefit from `.prefetch_related(Prefetch('student_modules', queryset=StudentModule.objects.select_related('module', 'local_assessment')))`, added to this view's base `students` queryset. Calling either property on a single `Student` fetched without that prefetch still works correctly, just costs a query per module instead of being free — the fix is purely additive, not a behavior change.
- **Trainer Roster: 122 queries → 12.** Same root cause (`is_evaluated`/`is_competent` called per student, once per trainer's roster) plus a missing `select_related('applicant', 'applicant__program')` on `trainer.students.filter(...)`. Same `Prefetch` pattern applied per-trainer.
- **Dashboard: 63 → 24.** The International Exams table's per-student exam-history modal used to run a fresh `InternationalExamAttempt` query *per student in the loop* building `student_rows`. Replaced with one query for every attempt across every student, grouped by student id in Python.
- **Alumni page: 14 → 7.** Same pattern — a fresh "passed certs" query per alumnus, replaced with one query for all of them grouped in Python.
- **Attendance register: 29 → 18.** The MTD attendance rate was 2 fresh `COUNT` queries *per student in the class*. Replaced with one query for the whole month across the whole class, grouped in Python — careful to still run each student's `get_or_create` (auto-creates today's record, defaulting to Present) *before* that batch query, so a record created for the first time on this exact page load is still correctly counted in that same load's MTD rate, not just from the next reload onward.
- **Excel export** (`admissions.views._filtered_student_rows`, shared with the Student List page) got the same `student_modules` `Prefetch` added, since `student.is_competent` is checked per exported row — this one hadn't been measured yet, but was the same shape of bug.
- Every fix was verified two ways: query count before/after (via `connection.queries`), and that the actual computed numbers (pass rates, MTD rates, etc.) are bit-for-bit identical to before the change — this was a query-plan optimization, not a logic change.
- **Not chased further**: the dashboard's remaining ~24 queries are legitimate — one distinct small aggregate (`COUNT`/`AVG`/`GROUP BY`) per stat card, not a loop-driven N+1. Squeezing those into fewer round trips is possible but low value next to what was already fixed.

### ✅ Refactor — Django messages centralized (fixes "notifications keep popping up twice")
- **Root cause**: `templates/base.html` and 15+ major page templates (Dashboard, Student List, Student Profile, Grading, Alumni, Trainer Roster, among others) never rendered `{% if messages %}` at all, while 10 other templates each carried their own slightly-different duplicate of that block. Django's messages framework keeps a message queued across requests until it's actually rendered — so a message routed through a page that renders no messages block (e.g. a role-check decorator's redirect, which lands on the Dashboard) sat queued and only surfaced later on whatever page the user happened to visit next that *did* render messages. If the same blocked action was attempted twice in the meantime, both queued messages appeared stacked together on that later page — exactly the "Only Test Admins can access international exam records." showing twice, reported by the client.
- **Fix**: added one centralized messages block to `templates/base.html`, rendered immediately before `<main>` on every page, then deleted the 10 duplicated per-template copies (`academics/attendance.html`, `academics/settings.html`, `accounts/user_list.html`, `admissions/application_detail.html`, `admissions/application_list.html`, `admissions/base_form.html`, `assessments/booking_list.html`, `assessments/exam_attempt_form.html`, `assessments/exam_attempt_list.html`, `assessments/platform_management.html`). Confirmed via a repo-wide search that `base.html` is now the only template containing the block.
- **Verified**: a Trainer hitting a Test-Admin-only URL (`/assessments/exams/`) now redirects `/assessments/exams/` → `/dashboard/` → `/` → `/assessments/grading/`, with the error message appearing exactly once on the final landing page (confirmed via `Client(follow=True)` and counting message occurrences in the response body — count was 1, not 0, not 2). Also spot-checked that a *successful* action's message (`Campus added successfully.`) still renders correctly on the Settings page now that its old per-template block is gone, and that previously messageless pages (Dashboard, Student List, Alumni) still return 200 with no regressions.

### ✅ Refactor — role-check decorators consolidated
- **Root cause**: `exec_only`, `trainer_only`, and `test_admin_only` each existed as a separate, near-identical private function copy-pasted into whichever view file first needed them — `accounts.views.exec_only`, `academics.views.exec_only`, `academics.views.trainer_only`, `assessments.views.trainer_only`, `assessments.views.test_admin_only` — five function bodies differing only in which `SystemUser` role attribute they checked, which message they flashed, and which URL they redirected to on failure.
- **Fix**: added `accounts/decorators.py` with one `role_required(role_attr, message, redirect_to)` factory holding the actual check-flash-redirect logic. Each app now builds its own bare `exec_only`/`trainer_only`/`test_admin_only` name at import time by calling the factory once with that app's own message and redirect target (e.g. `trainer_only = role_required('is_trainer', "Only Trainers can access grading.", 'dashboard:index')`) — every one of the 33 existing `@exec_only`/`@trainer_only`/`@test_admin_only` call sites across `accounts/views.py`, `academics/views.py`, and `assessments/views.py` needed no change at all, since the decorator is still used bare.
- **Deliberately not touched**: `admissions/views.py` has no decorator to consolidate here — its permission checks are inline `if not (request.user.is_exec_admin or request.user.is_data_capturer):`-style role *combinations* that vary per view, not a single repeated role check, so forcing them into `role_required` would either lose the OR-logic or bloat the factory for one file's benefit.
- **Verified**: for all five consolidated decorators, confirmed via `Client` requests that a disallowed role still gets redirected to the exact same URL with the exact same flashed message as before the refactor, and that the allowed role for each still gets a normal 200.

### ✅ Refactor — modal show/hide JS consolidated
- **Root cause**: every popup dialog in the app (grading entry, add-module, add-column, add-student, exam history, new registrations, plus the `itcaConfirm` themed confirm dialog) toggled the same two Tailwind classes (`hidden` off + `flex` on to show, reversed to hide) via its own copy-pasted `openXModal()`/`closeXModal()` pair — about 8 near-identical function bodies spread across `dashboard/index.html`, `assessments/grading.html`, `assessments/platform_management.html`, and `admissions/student_detail.html` (the last of these already had a generic `openModal(id)`/`closeModal(id)` pair, just not shared app-wide).
- **Fix**: added two globals, `showModal(id)`/`hideModal(id)`, to `templates/base.html` (next to the `itcaConfirm` dialog, which now calls them too instead of duplicating the same two lines a third time). Page-specific open functions that do real pre-population work (`openGradingModal` filling in a student's marks, `openExamHistoryModal` building a past-attempts table, `openAddColumnModal`/`openAddStudentModal` setting a form's target URL) were kept, but now end with a call to `showModal(id)` instead of repeating the two `classList` lines. Close functions with no extra logic (`closeNewRegistrationsModal`, `closeExamHistoryModal`, `closeAddModuleModal`, and `platform_management.html`'s local `closeModal`) were deleted outright — their `onclick` call sites now call `hideModal('theModalId')` directly. `closeGradingModal` was kept (it also clears `currentButton`, and is called from JS after a successful save, not just from a button) but its body now just calls `hideModal('gradingModal')`.
- **Verified**: `manage.py check` passes, and a `Client` request to each of the four templates confirms the expected `showModal(...)`/`hideModal(...)` calls are present in the rendered HTML and the corresponding old `openXModal`/local `openModal(`/`closeXModal` definitions are gone.

### ✅ Refactor — `admissions/views.py` split into a package
- **Root cause**: `admissions/views.py` had grown to ~960 lines covering four genuinely separate concerns (the application form pipeline, historical onboarding, the student list/detail/export, and Alumni), which made it the largest file in the codebase by a wide margin and the hardest to navigate.
- **Fix**: turned it into a package, `admissions/views/`, with one module per concern — `applications.py` (the multi-step form + Exec Admin review pipeline: `application_step`, `application_list`, `application_detail`, `application_approve`, `application_reject`, `application_submit`, plus the `STEPS`/`TOTAL_STEPS` config it owns), `onboarding.py` (`onboard_confirm` — the historical-onboarding finishing step; `application_step` itself stays in `applications.py` since it's shared with a normal application), `students.py` (`student_list`, `student_export`, `student_detail`, `student_set_email`, `student_module_add`, `student_delete`, and their shared `_filtered_student_rows`/`_delete_student_and_records` helpers), and `alumni.py` (`alumni_list`). `admissions/views/__init__.py` re-exports every name from all four, so `admissions/urls.py`'s existing `from . import views` / `views.<name>` references needed zero changes — this was a purely structural split, not a behavior change. Also dropped two genuinely-unused imports surfaced while splitting (`datetime.date as date_cls` and `StudentContact`, neither referenced anywhere in the original file's body).
- **Verified**: `manage.py check` and `makemigrations --check --dry-run` both pass; a `Client` hit every view across all four new modules (`application_list`, `application_new`, `application_detail`, `onboard_new`, `student_list`, `student_detail`, `student_export`, `alumni_list`) and got 200; and two write paths (`student_set_email`, `student_module_add`) were exercised through a real POST inside a rolled-back transaction to confirm the split modules still save correctly, not just render.

### ✅ Refactor — Settings page context builders merged
- **Root cause**: `academics/views.py` had two separate functions building the same settings-page context dict — `settings_index` (the plain GET) and `_settings_context(**overrides)` (called by `campus_add`/`program_add`/`module_add`/`program_module_add`/`class_add`/`calendar_update` to re-render the settings page in place after a form validation error). They'd drifted apart: `settings_index` read `?module_q=` and `?tab=` from the request to filter the Modules tab and preserve which tab was open, but `_settings_context` had no `request` parameter at all, so a validation error on *any* add form silently dropped an active module search back to the unfiltered list and reset the tab to whatever the call site hardcoded — a real, if minor, inconsistency, not just duplicated code.
- **Fix**: `_settings_context` now takes `request` as its first argument and is the single place both the module-search filtering and the tab default live; `settings_index` was reduced to a one-line call into it. All 6 call sites were updated to pass `request` through.
- **Verified**: confirmed the exact bug this fixes no longer reproduces — submitting an invalid Campus-add form while `?module_q=Security&tab=campuses` was in the query string now still shows "Security" in the re-rendered module search box (previously it wouldn't have, since `_settings_context` had no request to read it from). Also re-ran the plain settings GET, and one full add-flow per tab (Campus/Program/Module) via a real POST in a rolled-back transaction, confirming saves still work correctly, not just the error-path rendering.

### ✅ Containerized for deployment (Azure Container Apps)
- `Dockerfile`, `.dockerignore`, `entrypoint.sh` (runs `migrate` + `collectstatic` on every container start, then `gunicorn`)
- `requirements.txt` gained `gunicorn` and `whitenoise`
- `itca_sms/settings.py`: `SECURE_PROXY_SSL_HEADER` (Container Apps' ingress terminates HTTPS and proxies over plain HTTP — without this Django thinks every request is insecure), `CSRF_TRUSTED_ORIGINS` (derived from `ALLOWED_HOSTS`), `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` gated on `DEBUG=False`, whitenoise middleware + `STORAGES['staticfiles']` for compressed/hashed static file serving with no separate storage account needed, and `DB_SSL_REQUIRE` env flag (Azure Postgres requires SSL, the local Docker container doesn't have it configured at all)
- `/healthz/` — unauthenticated, no-DB-query endpoint for Container Apps' liveness/readiness probes (`itca_sms/urls.py`)
- **Chose Docker Hub over Azure Container Registry** for the image, to keep the whole stack genuinely free (ACR's cheapest tier isn't free; Docker Hub's free tier — 1 private repo, unlimited public — is more than enough for a single low-traffic Container App image)

### ✅ Deployed to Azure Container Apps — live (2nd deployment, original decommissioned)
The original deployment (`itca-sms-app.wittybeach-44e8382e...`, server `itca-postgres26`, client ID `edd416a4-...`) was fully decommissioned by the client before this one — resource group, Postgres server, Docker Hub image, and Entra ID App Registration were all gone, so this was a from-scratch provision, not a redeploy onto old infra. The Azure AD tenant itself is unchanged throughout (`andreitcaoutlook.onmicrosoft.com`, tenant ID `e49e26bc-5514-4444-8845-7245d593b97d`).

- **Subscription is Pay-As-You-Go, not a free-trial account** — this matters because Azure Database for PostgreSQL's well-known "free for 12 months" benefit (750 hrs Burstable B1MS + 32GB) only applies to free-trial accounts. On PAYG, Postgres bills from hour one no matter what — confirmed via `az rest` against the subscription's `quotaId` (`PayAsYouGo_2014-09-01`) before provisioning anything, rather than assuming the free tier applied like last time. Client explicitly chose to accept this small ongoing cost (smallest available tier) rather than self-host Postgres in a container or move to a third-party free tier, to keep the architecture simple and matching what was asked for ("Azure for Postgres").
- **Live URL**: `https://itca-sms-app.agreeabledune-f00b9559.southafricanorth.azurecontainerapps.io` — resource group `itca-sms-rg`, region `southafricanorth`
- **Database**: Azure Database for PostgreSQL Flexible Server, Burstable B1MS (cheapest paid tier — genuinely free tier isn't available on this subscription, see above), 32GB storage, server `itca-sms-pg.postgres.database.azure.com`, database `itca_db`, admin user `itca_sms_admin`. Firewall allows Azure services plus the client's own IP for direct `psql` access. Fresh database — no data migrated from anywhere, since the prior deployment's data was decommissioned along with it.
- **Image**: `siphelelemsane/itca-sms:latest` on Docker Hub (public repo, recreated fresh since the old one was gone). Deployment is Manual, not continuous — a new `:latest` push needs `az containerapp update --image ...` (or a Portal "Create new revision") to actually roll out.
- **Container App config**: Consumption plan, 0.5 CPU / 1Gi memory, ingress on port 8000, health probe path `/healthz/`, min replicas 0 / max replicas 1 for scale-to-zero — confirmed this stays within Container Apps' standing free monthly grant (180,000 vCPU-seconds / 360,000 GiB-seconds / 2M requests, which applies per-subscription regardless of account type, unlike Postgres).
- **Postgres admin password and the Container App's `SECRET_KEY`/Entra client secret were generated directly into local files and referenced into `az` commands via shell substitution (`$(cat file)`) — none of the three ever appeared as plaintext in any command output or chat text**, and the local files were deleted immediately after use. This was a deliberate fix for the exact issue flagged against the previous deployment (its Postgres password "went through chat in plain text during setup").
- **Azure AD App Registration** — "ITCA SMS Portal", client ID `c429b00c-efe5-4971-95cc-ed3811a55ed5`. Sign-in audience deliberately set to `AzureADandPersonalMicrosoftAccount` (`AZURE_AD_TENANT_ID=common`) per client's explicit choice, same as the previous deployment — personal Microsoft accounts can sign in and land as Data Capturers. Redirect URIs registered for both `http://localhost:8000/oidc/callback/` (local dev) and the live app's `/oidc/callback/`. Verified end-to-end: hit `/oidc/authenticate/` and confirmed the resulting Microsoft authorize URL carries the exact right `client_id`/`redirect_uri`/`tenant=common`, then the client did an actual interactive sign-in, which succeeded.
- A Django superuser (for `/admin/` emergency access, separate from Entra SSO) was created by the client directly via `az containerapp exec ... python manage.py createsuperuser`, run in their own terminal so the password was never typed anywhere I could see it.
- **Deliberate decision**: `AZURE_AD_TENANT_ID` stays on `common` for now (the client's explicit, repeated choice) — revert to the real tenant GUID and restrict the App Registration to single-tenant-only whenever personal-account access is no longer wanted.

### 🔲 Testing
- No automated tests written yet — recommend adding as features stabilize, particularly around the approval/capacity logic and assessment average calculations
- A full-lifecycle manual QA pass **was** run against the live DB (not automated, not rolled back — the client asked to review the resulting data themselves before it's cleared): 40 students seeded (20 per campus, uneven class sizes 2-9 across both programs/cohorts on purpose), split across all three ways a student can enter the system (fresh Application → Approve, historical onboarding into New, historical onboarding straight into Returning), 5 of them promoted New → Returning via the real time-based mechanism, 30 international exam attempts recorded (including 5 fail-then-resit pairs to check attempt numbering), 6 exam bookings, and NQF5 grading exercised both ways (full-Competent → graduated 8 to Alumni; partially-graded → correctly stayed Returning). Every Dashboard and Reports stat was cross-checked against a hand-computed ground truth from the raw data and matched exactly (pending applications, new registrations, active students, per-program splits, pass rate, avg attempts to pass, not-yet-attempted, cert-pass-by-body) — no computation bugs found. Two real issues were found and only one fixed (the other flagged, not touched, pending client input):
  - **Fixed**: the Grading page's empty state said "No students assigned to you yet" for a trainer who actually has students, just none currently in their Returning year (or all of them already graduated) — genuinely misleading, since it reads as "you have zero students" rather than "nothing to grade right now." Reworded in `templates/assessments/grading.html`.
  - **Flagged as "Enterprise shows a flat 0% pass rate" — resolved by the client removing the Bushbuckridge campus and Enterprise program outright**, rather than a code fix. No longer applicable.
  - Also worth a look, lower priority: a graduated student's own profile page (`student_detail`) shows no "Graduated"/Alumni indicator anywhere near the top — the Enrollment History table further down does show their enrollment as `Completed`, and the Alumni list page does show a "Graduated" tag, but the profile itself gives no immediate visual cue that this student is now an alumnus rather than still active.

---

## 7. Known Technical Notes

- **Python 3.14 + Django 6.1** currently in use (upgraded from Django 5.0 due to a `super()` compatibility issue in the admin template engine under Python 3.14).
- ~~The live DB has a third campus ("Bushbuckridge"/BBR) and a third program ("Enterprise"/ENT)~~ — **the client has since removed both** via Settings. The app is back to the documented two-campus ("Durban"/DBN, "Pietermaritzburg"/PMB), two-program ("Cyber Security"/CYB, "Software Development"/SFTW) setup everywhere.
- **Windows development environment** — commands documented account for `venv\Scripts\activate`, `mkdir` without `-p`, and PowerShell/CMD path syntax.
- **`requirements.txt`** now exists (it didn't originally) — generated via `pip freeze`, includes `openpyxl` for the Excel export. Keep it updated when adding packages; it'll matter for containerizing the app before Azure deployment.
- **Migrations must stay in sync with `models.py`** — a past session edited models (the `LocalAssessment` redesign, `Student.student_id_code`) without ever running `makemigrations`/`migrate`, which went unnoticed until a full QA pass hit `ProgrammingError: column ... does not exist` on a live query. Always run `python manage.py makemigrations --check --dry-run` after model changes, before assuming a feature works.
- **The `assign_default_modules` signal was documented as built but didn't exist** until this was caught in QA — `admissions/models.py` imported `post_save`/`receiver` but never registered a receiver, so approving an application never auto-assigned default modules or created assessment slots. Now implemented at the bottom of `admissions/models.py`.
- **Azure's loopback redirect URI rule**: for plain-HTTP local redirect URIs, Azure only accepts the literal host `localhost`, not `127.0.0.1`. Always browse to `http://localhost:8000/...` locally, not `127.0.0.1`, to match the registered redirect URI.
- **Demo student data was fully reset**, per client instruction — every pre-existing `Student` (and their `Applicant`/`Enrollment`/`StudentModule`/etc.) was deleted and replaced with exactly 5 students in each of the 8 Campus × Program × Cohort combinations (Durban/Pietermaritzburg × Cyber Security/Software Development × New/Returning = 40 students), using `admissions.views._delete_student_and_records` for cleanup and the historical-onboarding `Student`/`Enrollment` creation pattern for the reseed, run once via a one-off script (not a permanent management command). This also required creating Pietermaritzburg's 4 classes from scratch (`Mvuzo Mndawe` → Cyber Security, `Zibuyile Msane` → Software Development, both cohorts, academic year 2026) — PMB had zero classes configured despite being an active campus.
- **No task scheduler in this app** (no Celery, no cron) — the time-based New → Returning promotion (see "Student Lifecycle") is triggered lazily from the Exec Admin dashboard's own view function on every load as a stopgap, with `python manage.py promote_new_cohort_students` available for a real scheduled trigger to call instead once one exists (an Azure Container Apps Job is the natural fit, given the app's already on ACA). Worth revisiting before this matters for a real academic year end date in production.

---

## 8. Suggested Next Session Priorities

1. Revert `AZURE_AD_TENANT_ID` to the real tenant GUID and restrict the Azure App Registration back to single-tenant-only, once the client is done wanting personal-account access in production (currently a deliberate choice, not an oversight — see §6)
2. Unsuccessful application purging (1-year retention job)
3. Automated tests, especially around approval/capacity logic and assessment averages
4. The application-approval capacity check (`application_approve`) reads `enrolled_count >= active_class.capacity` then creates the enrollment in a separate statement — wrapped in `@transaction.atomic` but not `select_for_update()`, so two Exec Admins approving into the same near-full class at the exact same instant could theoretically both pass the check. Low risk given how few Exec Admins there are and how rarely that'd coincide, but worth closing with a row lock if it's ever a concern.
