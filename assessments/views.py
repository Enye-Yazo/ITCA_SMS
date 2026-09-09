# assessments/views.py

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from .models import (
    StudentModule, LocalAssessment, InternationalExamAttempt,
    PlatformTable, PlatformColumn, PlatformRow, PlatformRowValue,
)
from .forms import InternationalExamAttemptForm
from admissions.models import Student

# Exec Admins are redirected to the dashboard rather than granted access
# here — grading is scoped to a trainer's own students.
trainer_only = role_required('is_trainer', "Only Trainers can access grading.", 'dashboard:index')


# ─── Grading Matrix ─────────────────────────────────────────────────────────
@login_required
@trainer_only
def grading_index(request):
    """
    NQF5 competency matrix: one row per student, one column per NQF5
    (local-assessment) module assigned to any of the trainer's students —
    replacing the earlier one-row-per-module-per-student PFA/PSA table
    (which also, as a bug, showed every module including international-
    exam-only ones, since it never filtered on `is_local_assessment`).

    Only Returning-cohort students appear here — a New-cohort student's
    first year is Int. Cert-focused; NQF5 only comes into effect once
    they're Returning (see academics.models.run_end_of_year_promotion,
    the time-based New -> Returning promotion, and
    assessments.models.auto_graduate_on_full_nqf5_pass, which graduates
    a Returning student to Alumni once every NQF5 module is Competent).
    A New-cohort student's NQF5 modules are still assigned underneath
    (so they're ready the moment the student becomes Returning), just
    not shown here yet.

    Clicking a cell opens a modal (grade_update, AJAX) to rate that
    module Competent / Not Yet Competent with an optional comment; the
    cell then shows just "C" or "NYC".
    """
    from academics.models import Enrollment, Class

    student_modules = (
        StudentModule.objects
        .select_related('student', 'student__applicant', 'module', 'local_assessment')
        .filter(
            student__trainer=request.user,
            module__is_local_assessment=True,
            student__enrollments__status=Enrollment.EnrollmentStatus.ACTIVE,
            student__enrollments__class_group__cohort=Class.CohortChoices.RETURNING,
        )
        .distinct()
        .order_by('student__student_id_code', 'module__module_code')
    )

    students = {}
    modules = {}
    by_key = {}
    for sm in student_modules:
        students.setdefault(sm.student_id, sm.student)
        modules.setdefault(sm.module_id, sm.module)
        by_key[(sm.student_id, sm.module_id)] = sm

    module_list = sorted(modules.values(), key=lambda m: m.module_code)

    rows = []
    for student_id, student in sorted(students.items(), key=lambda kv: kv[1].student_id_code):
        cells = []
        for module in module_list:
            sm = by_key.get((student_id, module.id))
            assessment = getattr(sm, 'local_assessment', None) if sm else None
            cells.append({
                'student_module_id': sm.id if sm else None,
                'module_code': module.module_code,
                'competency': assessment.competency if assessment else None,
                'comment': assessment.comment if assessment else '',
            })
        rows.append({'student': student, 'cells': cells})

    return render(request, 'assessments/grading.html', {
        'rows': rows, 'module_list': module_list,
    })


# ─── Grade Update (AJAX) ────────────────────────────────────────────────────
@login_required
@trainer_only
@require_POST
def grade_update(request, student_module_id):
    """
    Sets the Competent / Not Yet Competent rating (+ optional comment)
    for a single StudentModule's NQF5 assessment. Only the trainer
    assigned to the student may update it — enforced below, not just
    hidden in the UI, to prevent one trainer editing another's students
    via a guessed URL (IDOR).
    """
    student_module = get_object_or_404(
        StudentModule.objects.select_related('student', 'module'),
        pk=student_module_id
    )

    if student_module.student.trainer_id != request.user.id:
        return JsonResponse(
            {'success': False, 'error': "You may only grade your own students."},
            status=403
        )

    if not student_module.module.is_local_assessment:
        return JsonResponse(
            {'success': False, 'error': "This module isn't an NQF5 local assessment."},
            status=400
        )

    from academics.models import Enrollment, Class
    active_enrollment = Enrollment.objects.filter(
        student=student_module.student, status=Enrollment.EnrollmentStatus.ACTIVE
    ).select_related('class_group').first()
    if not active_enrollment or active_enrollment.class_group.cohort != Class.CohortChoices.RETURNING:
        return JsonResponse(
            {'success': False, 'error': "NQF5 is only assessed once a student reaches their Returning year."},
            status=400
        )

    try:
        payload = json.loads(request.body or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'error': "Invalid request body."}, status=400)

    competency = payload.get('competency') or None
    if competency not in (None, *LocalAssessment.Competency.values):
        return JsonResponse(
            {'success': False, 'error': "Select Competent or Not Yet Competent."},
            status=400
        )

    comment = (payload.get('comment') or '').strip()

    assessment, _ = LocalAssessment.objects.get_or_create(student_module=student_module)
    assessment.competency = competency
    assessment.comment = comment
    assessment.trainer = request.user
    assessment.assessment_date = timezone.now().date()
    assessment.save()

    if assessment.competency == LocalAssessment.Competency.COMPETENT:
        label = 'C'
    elif assessment.competency == LocalAssessment.Competency.NOT_YET_COMPETENT:
        label = 'NYC'
    else:
        label = '—'

    return JsonResponse({
        'success': True,
        'competency': assessment.competency,
        'comment': assessment.comment,
        'label': label,
    })


test_admin_only = role_required(
    'is_test_admin', "Only Test Admins can access international exam records.", 'dashboard:index'
)


# ─── International Exam Attempts ────────────────────────────────────────────
@login_required
@test_admin_only
def exam_attempt_list(request):
    """
    History of every international exam attempt, newest first.
    Filterable by module code and pass/fail result.
    """
    attempts = InternationalExamAttempt.objects.select_related(
        'student_module__student', 'student_module__student__applicant',
        'student_module__module',
    ).order_by('-exam_date', '-attempt_number')

    module_filter = request.GET.get('module', 'all')
    result_filter = request.GET.get('result', 'all')

    if module_filter != 'all':
        attempts = attempts.filter(student_module__module__module_code=module_filter)
    if result_filter == 'passed':
        attempts = attempts.filter(exam_result=True)
    elif result_filter == 'failed':
        attempts = attempts.filter(exam_result=False)

    from academics.models import Module
    modules = Module.objects.filter(is_international_assessment=True).order_by('module_code')

    # Grouped by student for the expandable card list view — built from the
    # same filtered/ordered queryset the flat table uses, so both views
    # always agree on which attempts are shown.
    student_groups = {}
    student_order = []
    for attempt in attempts:
        student = attempt.student_module.student
        if student.id not in student_groups:
            student_groups[student.id] = {
                'student': student,
                'attempts': [],
                'passed_count': 0,
                'failed_count': 0,
            }
            student_order.append(student.id)
        group = student_groups[student.id]
        group['attempts'].append(attempt)
        if attempt.exam_result:
            group['passed_count'] += 1
        else:
            group['failed_count'] += 1

    grouped_attempts = [student_groups[sid] for sid in student_order]

    context = {
        'attempts': attempts,
        'grouped_attempts': grouped_attempts,
        'modules': modules,
        'filters': {'module': module_filter, 'result': result_filter},
    }
    return render(request, 'assessments/exam_attempt_list.html', context)


@login_required
@test_admin_only
@transaction.atomic
def exam_attempt_record(request):
    """
    Records a new international exam attempt. Student and Module are
    chosen independently of any existing StudentModule — if the student
    isn't already linked to that module (e.g. it's not one of their
    defaults), one is created here as an Elective assignment, since
    recording an exam attempt is exactly the kind of thing that should
    establish that link rather than require it to already exist.
    The attempt number is computed automatically — sequential per
    student+module — never entered by hand.
    """
    if request.method == 'POST':
        form = InternationalExamAttemptForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data['student']
            module = form.cleaned_data['module']

            student_module, _ = StudentModule.objects.get_or_create(
                student=student,
                module=module,
                defaults={'assignment_type': StudentModule.AssignmentType.ELECTIVE},
            )

            attempt = form.save(commit=False)
            attempt.student_module = student_module
            attempt.pass_threshold = form.cleaned_data['pass_threshold']
            # Pass/Fail is never picked by hand — the system compares the
            # score against the threshold entered for this exam.
            attempt.exam_result = attempt.score >= attempt.pass_threshold
            existing_attempts = InternationalExamAttempt.objects.filter(
                student_module=student_module
            ).count()
            attempt.attempt_number = existing_attempts + 1
            attempt.save()

            result = "Passed" if attempt.exam_result else "Failed"
            messages.success(
                request,
                f"Recorded attempt {attempt.attempt_number} for "
                f"{student.full_name} — {module.module_code} "
                f"({attempt.score}/1000, threshold {attempt.pass_threshold} — {result})."
            )
            return redirect('assessments:exam_attempt_list')
    else:
        form = InternationalExamAttemptForm()

    students = Student.objects.select_related('applicant').order_by(
        'applicant__first_name', 'applicant__last_name'
    )
    return render(request, 'assessments/exam_attempt_form.html', {
        'form': form,
        'students': students,
    })


# ── Exam Bookings ──────────────────────────────────────────────────────────
@login_required
@test_admin_only
def booking_list(request):
    """
    Upcoming and past exam bookings, newest first. Test Admin creates a
    booking here ahead of time, then records the actual result later via
    Exam Results once the sitting has happened.
    """
    from .models import ExamBooking
    from .forms import ExamBookingForm

    if request.method == 'POST':
        form = ExamBookingForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data['student']
            module = form.cleaned_data['module']
            student_module, _ = StudentModule.objects.get_or_create(
                student=student, module=module,
                defaults={'assignment_type': StudentModule.AssignmentType.ELECTIVE},
            )
            booking = form.save(commit=False)
            booking.student_module = student_module
            booking.booked_by = request.user
            booking.save()
            messages.success(request, f"Exam booked for {student.full_name} - {module.module_code}.")
            return redirect('assessments:booking_list')
    else:
        form = ExamBookingForm()

    bookings = ExamBooking.objects.select_related(
        'student_module__student__applicant', 'student_module__module'
    ).order_by('exam_date', 'exam_time')

    upcoming = bookings.filter(status=ExamBooking.BookingStatus.SCHEDULED)

    # -- Month calendar grid --------------------------------------------------
    import calendar as cal_module
    from datetime import date as date_cls

    today = date_cls.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    bookings_by_day = {}
    for b in bookings.filter(exam_date__year=year, exam_date__month=month):
        bookings_by_day.setdefault(b.exam_date.day, []).append(b)

    cal = cal_module.Calendar(firstweekday=0)  # Monday first
    weeks = []
    for week in cal.monthdayscalendar(year, month):
        week_rows = []
        for day in week:
            week_rows.append({
                'day': day,
                'bookings': bookings_by_day.get(day, []) if day else [],
            })
        weeks.append(week_rows)

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year

    context = {
        'bookings': bookings, 'upcoming': upcoming, 'form': form,
        'weeks': weeks,
        'month_label': date_cls(year, month, 1).strftime('%B %Y'),
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
    }
    return render(request, 'assessments/booking_list.html', context)


# ── Trainer Int. Cert view (read-only) ───────────────────────────────────────
@login_required
@trainer_only
def trainer_intcert_view(request):
    """
    Read-only view of international exam results for the trainer's own
    students - recorded by the Test Admin, trainers cannot edit here.
    """
    attempts = InternationalExamAttempt.objects.select_related(
        'student_module__student__applicant', 'student_module__module'
    ).filter(student_module__student__trainer=request.user).order_by('-exam_date')

    return render(request, 'assessments/trainer_intcert.html', {'attempts': attempts})


# ── Platform Management ──────────────────────────────────────────────────────
# Test Admin owns provisioning of student email accounts and external
# vendor learning-platform/lab credentials — see PlatformTable/PlatformColumn
# docstrings in models.py for why this is an EAV-style schema rather than a
# fixed model per vendor.
@login_required
@test_admin_only
def platform_management(request):
    """
    Two sections (Access Credentials, Labs), each a set of Test-Admin
    defined vendor tables. Name/Program Code/Student Email are read live
    off the linked Student on every row; every other column is a
    PlatformColumn value editable inline via platform_cell_update (AJAX).
    """
    tables = (
        PlatformTable.objects
        .prefetch_related('columns', 'rows__student__applicant', 'rows__student__applicant__program',
                           'rows__values')
    )

    sections = {
        value: {'label': label, 'tables': []}
        for value, label in PlatformTable.Section.choices
    }

    for table in tables:
        columns = list(table.columns.all())
        row_data = []
        for row in table.rows.all():
            value_map = {v.column_id: v.value for v in row.values.all()}
            cells = [
                {'column': col, 'value': value_map.get(col.id, '')}
                for col in columns
            ]
            row_data.append({'row': row, 'student': row.student, 'cells': cells})
        sections[table.section]['tables'].append({
            'table': table, 'columns': columns, 'rows': row_data,
        })

    students = Student.objects.select_related('applicant', 'applicant__program').order_by(
        'applicant__first_name', 'applicant__last_name'
    )

    context = {
        'sections': sections,
        'students': students,
        'column_types': PlatformColumn.ColumnType.choices,
        'section_choices': PlatformTable.Section.choices,
    }
    return render(request, 'assessments/platform_management.html', context)


@login_required
@test_admin_only
@require_POST
def platform_table_create(request):
    """Adds a new vendor table under a section — the "add a vendor" escape hatch."""
    section = request.POST.get('section')
    vendor_name = request.POST.get('vendor_name', '').strip()

    if section not in PlatformTable.Section.values:
        messages.error(request, "Select a valid section.")
        return redirect('assessments:platform_management')
    if not vendor_name:
        messages.error(request, "Enter a vendor name.")
        return redirect('assessments:platform_management')
    if PlatformTable.objects.filter(section=section, vendor_name__iexact=vendor_name).exists():
        messages.error(request, f"A table for {vendor_name} already exists in that section.")
        return redirect('assessments:platform_management')

    order = PlatformTable.objects.filter(section=section).count()
    PlatformTable.objects.create(section=section, vendor_name=vendor_name, order=order)
    messages.success(request, f"Added {vendor_name} table.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_table_delete(request, table_id):
    table = get_object_or_404(PlatformTable, pk=table_id)
    vendor_name = table.vendor_name
    table.delete()
    messages.success(request, f"Deleted {vendor_name} table.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_column_create(request, table_id):
    """Adds a new column (e.g. another cert code) to an existing vendor table."""
    table = get_object_or_404(PlatformTable, pk=table_id)
    label = request.POST.get('label', '').strip()
    column_type = request.POST.get('column_type', PlatformColumn.ColumnType.TEXT)

    if not label:
        messages.error(request, "Enter a column name.")
        return redirect('assessments:platform_management')
    if table.columns.filter(label__iexact=label).exists():
        messages.error(request, f"{table.vendor_name} already has a column called {label}.")
        return redirect('assessments:platform_management')
    if column_type not in PlatformColumn.ColumnType.values:
        column_type = PlatformColumn.ColumnType.TEXT

    order = table.columns.count()
    PlatformColumn.objects.create(table=table, label=label, column_type=column_type, order=order)
    messages.success(request, f"Added column \"{label}\" to {table.vendor_name}.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_column_update(request, column_id):
    """Renames a column or changes its type (e.g. Text ↔ Password)."""
    column = get_object_or_404(PlatformColumn, pk=column_id)
    label = request.POST.get('label', '').strip()
    column_type = request.POST.get('column_type', column.column_type)

    if not label:
        messages.error(request, "Column name can't be empty.")
        return redirect('assessments:platform_management')
    if column.table.columns.filter(label__iexact=label).exclude(pk=column.pk).exists():
        messages.error(request, f"{column.table.vendor_name} already has a column called {label}.")
        return redirect('assessments:platform_management')

    column.label = label
    if column_type in PlatformColumn.ColumnType.values:
        column.column_type = column_type
    column.save()
    messages.success(request, "Column updated.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_column_delete(request, column_id):
    column = get_object_or_404(PlatformColumn, pk=column_id)
    label = column.label
    table_name = column.table.vendor_name
    column.delete()
    messages.success(request, f"Deleted column \"{label}\" from {table_name}.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_row_create(request, table_id):
    """Adds a student to a vendor table — one row per student per table."""
    table = get_object_or_404(PlatformTable, pk=table_id)
    student = Student.objects.filter(pk=request.POST.get('student_id')).select_related('applicant').first()

    if not student:
        messages.error(request, "Search for and select a student from the list.")
        return redirect('assessments:platform_management')

    row, created = PlatformRow.objects.get_or_create(table=table, student=student)
    if not created:
        messages.error(request, f"{student.full_name} is already in the {table.vendor_name} table.")
        return redirect('assessments:platform_management')

    messages.success(request, f"Added {student.full_name} to {table.vendor_name}.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_row_delete(request, row_id):
    row = get_object_or_404(PlatformRow, pk=row_id)
    student_name = row.student.full_name
    table_name = row.table.vendor_name
    row.delete()
    messages.success(request, f"Removed {student_name} from {table_name}.")
    return redirect('assessments:platform_management')


@login_required
@test_admin_only
@require_POST
def platform_cell_update(request):
    """
    AJAX endpoint — saves one cell's value (a PlatformColumn on one
    PlatformRow) as it's edited inline in the table, same pattern as
    grading's grade_update.
    """
    try:
        payload = json.loads(request.body or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'error': "Invalid request body."}, status=400)

    row = get_object_or_404(PlatformRow, pk=payload.get('row_id'))
    column = get_object_or_404(PlatformColumn, pk=payload.get('column_id'), table=row.table)
    value = (payload.get('value') or '').strip()

    PlatformRowValue.objects.update_or_create(row=row, column=column, defaults={'value': value})
    return JsonResponse({'success': True, 'value': value})
