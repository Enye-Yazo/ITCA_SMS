# dashboard/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q

from admissions.models import Applicant, Student
from academics.models import Program, Enrollment
from accounts.models import SystemUser, UserRole
from assessments.models import InternationalExamAttempt


@login_required
def dashboard_index(request):
    """
    Main dashboard view — Exec Admin only. Trainers, Test Admins and
    Data Capturers are routed to their own landing page (accounts:landing)
    straight after login and never see this view.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "The dashboard is only available to Exec Admins.")
        return redirect('accounts:landing')

    # ── Base querysets — Exec Admin sees every campus ─────────────────────────
    students = Student.objects.select_related(
        'applicant', 'applicant__campus',
        'applicant__program', 'trainer'
    ).filter(applicant__student_profile__isnull=False)

    active_enrollments = Enrollment.objects.filter(
        status=Enrollment.EnrollmentStatus.ACTIVE
    )

    # ── Stat Card Numbers ─────────────────────────────────────────────────────
    pending_applications = Applicant.objects.filter(
        application_status=Applicant.ApplicationStatus.PENDING
    ).count()

    # New registrations — students enrolled in the current academic year
    from django.utils import timezone
    current_year = timezone.now().year

    new_registration_enrollments = active_enrollments.filter(
        class_group__academic_year=current_year,
        class_group__cohort='New'
    ).select_related(
        'student', 'student__applicant', 'student__applicant__campus',
        'student__applicant__program', 'class_group'
    ).order_by('-start_date')

    new_registrations = new_registration_enrollments.count()

    # Rows for the "New Registrations" popup on the dashboard tile —
    # built here rather than in the template since it needs the same
    # queryset the stat card count is drawn from.
    new_registration_rows = [
        {
            'student_name': enrollment.student.full_name,
            'student_id_code': enrollment.student.student_id_code,
            'program_code': enrollment.student.program.program_code,
            'campus_code': enrollment.student.campus.campus_code,
            'start_date': enrollment.start_date,
        }
        for enrollment in new_registration_enrollments
    ]

    active_students = active_enrollments.count()

    # Per-program — used for stat card counts and the tile links through
    # to the filtered student list
    sftw_program = Program.objects.filter(program_code='SFTW').first()
    cyb_program = Program.objects.filter(program_code='CYB').first()

    sftw_students = active_enrollments.filter(
        class_group__program__program_code='SFTW'
    ).count()

    cyb_students = active_enrollments.filter(
        class_group__program__program_code='CYB'
    ).count()

    # ── Pass Rate Calculation ─────────────────────────────────────────────────
    # Based on international exam attempts across every student
    attempts = InternationalExamAttempt.objects.filter(
        student_module__student__in=students
    )
    total_attempts = attempts.count()
    passed_attempts = attempts.filter(exam_result=True).count()

    if total_attempts > 0:
        pass_rate = round((passed_attempts / total_attempts) * 100)
    else:
        pass_rate = 0

    fail_rate = 100 - pass_rate

    # ── Average Attempts to Pass ──────────────────────────────────────────────
    # How many sittings a certification typically takes once it's passed —
    # a distinct signal from raw pass rate (a cert can have a low pass rate
    # from first-time failures but still be passed quickly on the resit).
    avg_attempts_to_pass = attempts.filter(exam_result=True).aggregate(
        avg=Avg('attempt_number')
    )['avg']

    # ── Not Yet Attempted ──────────────────────────────────────────────────────
    # Active students who haven't sat a single international exam yet —
    # the thing a blended average would hide, surfaced directly instead.
    attempted_student_ids = attempts.values_list(
        'student_module__student_id', flat=True
    ).distinct()
    not_yet_attempted = students.exclude(id__in=attempted_student_ids).count()

    # ── Pass Rate by Certifying Body ──────────────────────────────────────────
    # Which vendor's certifications are actually the problem, rather than
    # one blended number — falls back to the module code for modules with
    # no certifying_body recorded.
    from django.db.models import Case, When, Value, CharField
    body_rows = list(
        attempts.annotate(
            body=Case(
                When(student_module__module__certifying_body__isnull=True, then='student_module__module__module_code'),
                When(student_module__module__certifying_body='', then='student_module__module__module_code'),
                default='student_module__module__certifying_body',
                output_field=CharField(),
            )
        )
        .values('body')
        .annotate(total=Count('id'), passed=Count('id', filter=Q(exam_result=True)))
        .order_by('-total')[:6]
    )
    for row in body_rows:
        row['pass_pct'] = round((row['passed'] / row['total']) * 100) if row['total'] else 0

    # ── Upcoming Bookings ──────────────────────────────────────────────────────
    from assessments.models import ExamBooking
    from django.utils import timezone as tz
    upcoming_bookings = ExamBooking.objects.filter(
        status=ExamBooking.BookingStatus.SCHEDULED,
        exam_date__gte=tz.now().date(),
    ).select_related(
        'student_module__student__applicant', 'student_module__module'
    ).order_by('exam_date', 'exam_time')[:5]

    # ── Student Table Rows — each student's most recent exam attempt ─────────
    student_rows = []
    for student in students:
        latest_attempt = InternationalExamAttempt.objects.filter(
            student_module__student=student
        ).select_related('student_module__module').order_by('-exam_date', '-attempt_number').first()

        if not latest_attempt:
            continue

        student_rows.append({
            'student_name': student.full_name,
            'program_code': student.program.program_code,
            'trainer_name': student.trainer.full_name if student.trainer else '—',
            'trainer_id':   student.trainer.id if student.trainer else '',
            'certification': latest_attempt.student_module.module.module_code,
            'score':        latest_attempt.score,
            'percentage':   latest_attempt.percentage_score,
            'passed':       latest_attempt.exam_result,
            'exam_date':    latest_attempt.exam_date,
        })

    # ── Filter Dropdowns ───────────────────────────────────────────────────────
    trainers = SystemUser.objects.filter(role=UserRole.TRAINER, is_active=True)
    programs = Program.objects.filter(is_active=True)

    # ── Context ───────────────────────────────────────────────────────────────
    context = {
        'stats': {
            'pending_applications': pending_applications,
            'new_registrations':    new_registrations,
            'active_students':      active_students,
            'sftw_students':        sftw_students,
            'cyb_students':         cyb_students,
            'pass_rate':            pass_rate,
            'fail_rate':            fail_rate,
            'total_attempts':       total_attempts,
            'avg_attempts_to_pass': avg_attempts_to_pass,
            'not_yet_attempted':    not_yet_attempted,
        },
        'student_rows': student_rows,
        'body_rows': body_rows,
        'upcoming_bookings': upcoming_bookings,
        'trainers':     trainers,
        'programs':     programs,
        'new_registration_rows': new_registration_rows,
        'sftw_program_id': sftw_program.id if sftw_program else '',
        'cyb_program_id':  cyb_program.id if cyb_program else '',
    }

    return render(request, 'dashboard/index.html', context)


@login_required
def reports_index(request):
    """
    Aggregate analytics across both campuses — NQF5 pass rate and
    certification progress broken down by program, plus the same
    headline numbers as the dashboard stat cards. Exec Admin only.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Reports are only available to Exec Admins.")
        return redirect('accounts:landing')

    students = Student.objects.select_related('applicant', 'applicant__program')
    total_students = students.count()

    programs = Program.objects.filter(is_active=True)
    program_rows = []
    for program in programs:
        program_students = students.filter(applicant__program=program)
        competent = sum(1 for s in program_students if s.is_competent)
        evaluated = sum(1 for s in program_students if s.formative_average is not None)
        pass_rate = round((competent / evaluated) * 100) if evaluated else 0
        program_rows.append({'program': program, 'pass_rate': pass_rate})

    total_attempts = InternationalExamAttempt.objects.count()
    passed_attempts = InternationalExamAttempt.objects.filter(exam_result=True).count()
    cert_pass_rate = round((passed_attempts / total_attempts) * 100) if total_attempts else 0

    from django.db.models import Count, Q
    module_rows = (
        InternationalExamAttempt.objects
        .values('student_module__module__module_code')
        .annotate(
            total=Count('id'),
            passed=Count('id', filter=Q(exam_result=True)),
        )
        .order_by('-total')[:6]
    )
    for row in module_rows:
        row['pass_pct'] = round((row['passed'] / row['total']) * 100) if row['total'] else 0

    evaluated_students = [s for s in students if s.formative_average is not None]
    overall_competent = sum(1 for s in evaluated_students if s.is_competent)
    overall_pass_rate = round((overall_competent / len(evaluated_students)) * 100) if evaluated_students else 0

    context = {
        'total_students': total_students,
        'overall_pass_rate': overall_pass_rate,
        'cert_pass_rate': cert_pass_rate,
        'program_rows': program_rows,
        'module_rows': module_rows,
    }
    return render(request, 'dashboard/reports.html', context)
