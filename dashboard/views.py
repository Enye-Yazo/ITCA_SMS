# dashboard/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q

from admissions.models import Applicant, Student
from academics.models import Program, Enrollment
from accounts.models import SystemUser, UserRole
from assessments.models import LocalAssessment, InternationalExamAttempt


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
    # Based on international exam attempts — most recent attempt per student
    total_attempts = InternationalExamAttempt.objects.filter(
        student_module__student__in=students
    ).count()

    passed_attempts = InternationalExamAttempt.objects.filter(
        student_module__student__in=students,
        exam_result=True
    ).count()

    if total_attempts > 0:
        pass_rate = round((passed_attempts / total_attempts) * 100)
    else:
        pass_rate = 0

    fail_rate = 100 - pass_rate

    # ── Student Table Rows ────────────────────────────────────────────────────
    # Build a list of dicts for the dashboard table
    student_rows = []

    # ── Summative Competency Calculation ──────────────────────────────────────
    # Blended pass rate: a student only counts once they have a formative
    # average recorded at all — students with no marks yet are excluded
    # rather than counted as Not Yet Competent.
    competent_count = 0
    evaluated_count = 0

    for student in students:
        # Get the most recent NQF5 mark for this student
        latest_local = LocalAssessment.objects.filter(
            student_module__student=student
        ).order_by('-assessment_date').first()

        # Get the most recent international exam score
        latest_int = InternationalExamAttempt.objects.filter(
            student_module__student=student
        ).order_by('-exam_date').first()

        student_rows.append({
            'student_name': student.full_name,
            'program_code': student.program.program_code,
            'trainer_name': student.trainer.full_name if student.trainer else '—',
            'trainer_id':   student.trainer.id if student.trainer else '',
            'nqf5_score':   latest_local.mark if latest_local else None,
            # International exams are scored out of 1000 (700 = pass) —
            # converted to a 0-100 percentage here since this column is
            # compared against the same >=80/>=60 thresholds as the
            # local NQF5 mark next to it.
            'int_score':    latest_int.percentage_score if latest_int else None,
        })

        if student.formative_average is not None:
            evaluated_count += 1
            if student.is_competent:
                competent_count += 1

    if evaluated_count > 0:
        competent_rate = round((competent_count / evaluated_count) * 100)
    else:
        competent_rate = 0

    not_competent_rate = 100 - competent_rate

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
            'competent_rate':       competent_rate,
            'not_competent_rate':   not_competent_rate,
            'evaluated_count':      evaluated_count,
        },
        'student_rows': student_rows,
        'trainers':     trainers,
        'programs':     programs,
        'new_registration_rows': new_registration_rows,
        'sftw_program_id': sftw_program.id if sftw_program else '',
        'cyb_program_id':  cyb_program.id if cyb_program else '',
    }

    return render(request, 'dashboard/index.html', context)
