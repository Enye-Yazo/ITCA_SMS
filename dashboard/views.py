# dashboard/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q

from admissions.models import Applicant, Student
from academics.models import Program, Enrollment
from accounts.models import SystemUser, UserRole
from assessments.models import LocalAssessment, InternationalExamAttempt


@login_required
def dashboard_index(request):
    """
    Main dashboard view.
    Exec Admin sees all campuses.
    Trainer sees only their campus and their students.
    """

    user = request.user

    # ── Base querysets filtered by role ───────────────────────────────────────
    if user.is_exec_admin:
        # Exec Admin sees everything
        students = Student.objects.select_related(
            'applicant', 'applicant__campus',
            'applicant__program', 'trainer'
        ).filter(applicant__student_profile__isnull=False)

        active_enrollments = Enrollment.objects.filter(
            status=Enrollment.EnrollmentStatus.ACTIVE
        )

    else:
        # Trainers see only their own students
        students = Student.objects.select_related(
            'applicant', 'applicant__campus',
            'applicant__program', 'trainer'
        ).filter(trainer=user)

        active_enrollments = Enrollment.objects.filter(
            status=Enrollment.EnrollmentStatus.ACTIVE,
            class_group__trainer=user
        )

    # ── Stat Card Numbers ─────────────────────────────────────────────────────
    pending_applications = Applicant.objects.filter(
        application_status=Applicant.ApplicationStatus.PENDING
    ).count()

    # New registrations — students enrolled in the current academic year
    from django.utils import timezone
    current_year = timezone.now().year

    new_registrations = active_enrollments.filter(
        class_group__academic_year=current_year,
        class_group__cohort='New'
    ).count()

    active_students = active_enrollments.count()

    # Per-program student counts
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
            'int_score':    latest_int.score if latest_int else None,
        })

    # ── Trainers List for Filter Dropdown ─────────────────────────────────────
    if user.is_exec_admin:
        trainers = SystemUser.objects.filter(
            role=UserRole.TRAINER,
            is_active=True
        )
    else:
        trainers = SystemUser.objects.filter(id=user.id)

    # ── Programs List for Filter Dropdown ─────────────────────────────────────
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
        },
        'student_rows': student_rows,
        'trainers':     trainers,
        'programs':     programs,
    }

    return render(request, 'dashboard/index.html', context)