# assessments/views.py

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import StudentModule, LocalAssessment, InternationalExamAttempt
from .forms import InternationalExamAttemptForm
from admissions.models import Student


def trainer_only(view_func):
    """
    Restricts a view to Trainers only.
    Exec Admins are redirected to the dashboard rather than granted
    access here — grading is scoped to a trainer's own students.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_trainer:
            messages.error(request, "Only Trainers can access grading.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─── Grading Table ──────────────────────────────────────────────────────────
@login_required
@trainer_only
def grading_index(request):
    """
    Table of every module a trainer's own students are studying,
    one row per StudentModule, with PFA01/PFA02/PSA columns.
    Clicking a row opens a popup (rendered client-side from the row's
    data attributes) to capture marks/competency for that module.
    """
    student_modules = (
        StudentModule.objects
        .select_related(
            'student', 'student__applicant', 'module',
        )
        .prefetch_related('local_assessments')
        .filter(student__trainer=request.user)
        .order_by('student__student_id_code', 'module__module_code')
    )

    rows = []
    for sm in student_modules:
        assessments = {a.assessment_type: a for a in sm.local_assessments.all()}
        pfa01 = assessments.get(LocalAssessment.AssessmentType.FORMATIVE_1)
        pfa02 = assessments.get(LocalAssessment.AssessmentType.FORMATIVE_2)
        psa = assessments.get(LocalAssessment.AssessmentType.SUMMATIVE)

        # Cohort comes from the student's most recent enrollment, if any
        latest_enrollment = sm.student.enrollments.order_by('-start_date').first()
        cohort = latest_enrollment.class_group.cohort if latest_enrollment else '—'

        rows.append({
            'student_module_id': sm.id,
            'student_id_code': sm.student.student_id_code,
            'student_name': sm.student.full_name,
            'cohort': cohort,
            'module_code': sm.module.module_code,
            'module_name': sm.module.module_name,
            'pfa01': pfa01,
            'pfa02': pfa02,
            'psa': psa,
        })

    return render(request, 'assessments/grading.html', {'rows': rows})


# ─── Grade Update (AJAX) ────────────────────────────────────────────────────
def _clean_mark(value):
    """Validates a mark is an integer 0-100, or returns None for blank input."""
    if value in (None, ''):
        return None
    try:
        mark = int(value)
    except (TypeError, ValueError):
        raise ValueError("Marks must be whole numbers.")
    if not (0 <= mark <= 100):
        raise ValueError("Marks must be between 0 and 100.")
    return mark


@login_required
@trainer_only
@require_POST
def grade_update(request, student_module_id):
    """
    Updates the 3 LocalAssessment records (PFA01, PFA02, PSA) for a single
    StudentModule in one submission. Only the trainer assigned to the
    student may update their records — enforced below, not just hidden
    in the UI, to prevent one trainer editing another's students via a
    guessed URL (IDOR).
    """
    student_module = get_object_or_404(
        StudentModule.objects.select_related('student'),
        pk=student_module_id
    )

    if student_module.student.trainer_id != request.user.id:
        return JsonResponse(
            {'success': False, 'error': "You may only grade your own students."},
            status=403
        )

    try:
        payload = json.loads(request.body or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'error': "Invalid request body."}, status=400)

    try:
        with transaction.atomic():
            assessments = {
                a.assessment_type: a
                for a in student_module.local_assessments.select_for_update().all()
            }

            # ── Formative 1 & 2 ────────────────────────────────────────────
            for key in (LocalAssessment.AssessmentType.FORMATIVE_1,
                        LocalAssessment.AssessmentType.FORMATIVE_2):
                assessment = assessments.get(key)
                if assessment is None:
                    continue
                data = payload.get(key, {})

                mark = _clean_mark(data.get('mark'))
                is_remediation = bool(data.get('is_remediation'))
                remediation_mark = _clean_mark(data.get('remediation_mark'))

                # A remediation attempt only makes sense once the original
                # mark exists and is below the 95% pass mark.
                if is_remediation and (mark is None or mark >= 95):
                    raise ValueError(
                        "Remediation can only be recorded for a formative "
                        "mark below 95%."
                    )

                assessment.mark = mark
                assessment.is_remediation = is_remediation
                assessment.remediation_mark = remediation_mark if is_remediation else None
                assessment.trainer = request.user
                assessment.assessment_date = timezone.now().date()
                assessment.save()

            # ── Summative ────────────────────────────────────────────────────
            psa = assessments.get(LocalAssessment.AssessmentType.SUMMATIVE)
            if psa is not None:
                data = payload.get(LocalAssessment.AssessmentType.SUMMATIVE, {})
                competent = data.get('competent')
                if competent not in (None, True, False, 'true', 'false'):
                    raise ValueError("Competency must be Competent or Not Yet Competent.")
                if isinstance(competent, str):
                    competent = competent == 'true'
                psa.competent = competent
                psa.trainer = request.user
                psa.assessment_date = timezone.now().date()
                psa.save()

    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    return JsonResponse({'success': True})


def test_admin_only(view_func):
    """Restricts a view to Test Admins only."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_test_admin:
            messages.error(request, "Only Test Admins can access international exam records.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


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
            existing_attempts = InternationalExamAttempt.objects.filter(
                student_module=student_module
            ).count()
            attempt.attempt_number = existing_attempts + 1
            attempt.save()

            messages.success(
                request,
                f"Recorded attempt {attempt.attempt_number} for "
                f"{student.full_name} — {module.module_code} "
                f"({attempt.score}/1000, {attempt.percentage_score}%)."
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
