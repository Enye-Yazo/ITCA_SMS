# dashboard/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Prefetch

from admissions.models import Applicant, Student
from academics.models import Program, Campus, Enrollment, run_end_of_year_promotion
from accounts.models import SystemUser, UserRole
from assessments.models import InternationalExamAttempt, StudentModule


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

    # There's no cron/Celery in this app — the Exec Admin's own dashboard
    # is the most reliable place to lazily check whether today has
    # reached the configured academic year end, since they load it
    # regularly. Cheap and idempotent: no-ops instantly once already run
    # for the current cycle. See academics.models.run_end_of_year_promotion.
    run_end_of_year_promotion()

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

    # ── Modules Needing Attention ──────────────────────────────────────────────
    # Replaces "Pass Rate by Certifying Body", which blended every module
    # under whichever vendor published it and didn't point at anything
    # specific to act on. Flags a module when more than 40% of the
    # students who've actually sat it still haven't passed — per
    # *student*, not per *attempt*: a student who failed once and then
    # passed on resit counts as a pass here, since they got there in the
    # end. Counting by attempt instead would unfairly flag a module where
    # every student eventually passes, just not on the first try.
    student_module_results = {}  # (module_code, module_name) -> {student_id: ever_passed}
    for a in attempts.values(
        'student_module__student_id',
        'student_module__module__module_code',
        'student_module__module__module_name',
        'exam_result',
    ):
        key = (a['student_module__module__module_code'], a['student_module__module__module_name'])
        students_for_module = student_module_results.setdefault(key, {})
        student_id = a['student_module__student_id']
        students_for_module[student_id] = students_for_module.get(student_id, False) or a['exam_result']

    modules_needing_attention = []
    for (module_code, module_name), results in student_module_results.items():
        total_students = len(results)
        failed_students = sum(1 for passed in results.values() if not passed)
        fail_pct = failed_students / total_students
        if fail_pct > 0.4:
            modules_needing_attention.append({
                'module_code': module_code,
                'module_name': module_name,
                'total_students': total_students,
                'failed_students': failed_students,
                'fail_pct': round(fail_pct * 100),
            })
    modules_needing_attention.sort(key=lambda r: (-r['fail_pct'], -r['total_students']))
    modules_needing_attention = modules_needing_attention[:5]

    # ── Pass Rate by Campus ──────────────────────────────────────────────────
    # Replaces "Upcoming Bookings", whose "View all bookings →" link pointed
    # at a Test-Admin-only page — an Exec Admin clicking it just bounced
    # back to the dashboard they were already on. International exam pass
    # rate compared per campus (not blended NQF5+Int Cert into one number)
    # — same scope as the "Cert Pass Rate" donut above, just split out to
    # answer "is one campus underperforming the others" rather than one
    # combined figure.
    #
    # Rendered as a sorted, scrollable bar list (like Modules Needing
    # Attention) rather than a fixed side-by-side grid — a 2-column grid
    # reads fine with exactly 2 campuses today, but stops working the
    # moment ITCA opens a 3rd, 4th, etc.
    campus_pass_rates = []
    for campus in Campus.objects.filter(is_active=True).order_by('campus_name'):
        campus_attempts = attempts.filter(student_module__student__applicant__campus=campus)
        campus_total = campus_attempts.count()
        campus_passed = campus_attempts.filter(exam_result=True).count()
        campus_pass_rates.append({
            'campus_name': campus.campus_name,
            'campus_code': campus.campus_code,
            'total': campus_total,
            'passed': campus_passed,
            'pass_rate': round((campus_passed / campus_total) * 100) if campus_total else None,
        })
    campus_pass_rates.sort(key=lambda c: (c['pass_rate'] is None, -(c['pass_rate'] or 0)))

    # A one-line summary is easier to compute here than with template
    # arithmetic — only meaningful once at least two campuses actually
    # have attempts to compare, and scales to any number of campuses
    # (not just exactly two).
    campus_comparison = None
    rated_campuses = [c for c in campus_pass_rates if c['pass_rate'] is not None]
    if len(rated_campuses) == 2:
        leader, other = rated_campuses[0], rated_campuses[1]
        diff = leader['pass_rate'] - other['pass_rate']
        if diff > 0:
            campus_comparison = f"{leader['campus_code']} leads {other['campus_code']} by {diff} point{'s' if diff != 1 else ''}"
        else:
            campus_comparison = "Both campuses are performing evenly"
    elif len(rated_campuses) > 2:
        highest, lowest = rated_campuses[0], rated_campuses[-1]
        if highest['pass_rate'] != lowest['pass_rate']:
            campus_comparison = (
                f"Highest: {highest['campus_code']} ({highest['pass_rate']}%) · "
                f"Lowest: {lowest['campus_code']} ({lowest['pass_rate']}%)"
            )
        else:
            campus_comparison = "All campuses are performing evenly"

    # ── Student Table Rows — each student's most recent exam attempt ─────────
    # One row per student (never one per attempt) — a student who's sat
    # several exams across different modules only ever shows their latest
    # here; clicking their name opens a modal with the full history
    # (all_attempts, below) instead of listing every attempt as its own row.
    # One query for every attempt across every student, grouped in Python
    # by student id — replaces what used to be a fresh
    # InternationalExamAttempt query *per student in the loop below*
    # (a textbook N+1: 40 students meant 40 extra queries here alone).
    attempts_by_student_id = {}
    for a in (
        InternationalExamAttempt.objects
        .filter(student_module__student__in=students)
        .select_related('student_module__module')
        .order_by('-exam_date', '-attempt_number')
    ):
        attempts_by_student_id.setdefault(a.student_module.student_id, []).append(a)

    student_rows = []
    for student in students:
        student_attempts = attempts_by_student_id.get(student.id)
        if not student_attempts:
            continue

        latest_attempt = student_attempts[0]

        student_rows.append({
            'student_id': student.id,
            'attempts_dom_id': f'attempts-data-{student.id}',
            'student_name': student.full_name,
            'program_code': student.program.program_code,
            'trainer_name': student.trainer.full_name if student.trainer else '—',
            'trainer_id':   student.trainer.id if student.trainer else '',
            'certification': latest_attempt.student_module.module.module_name,
            'score':        latest_attempt.score,
            'percentage':   latest_attempt.percentage_score,
            'passed':       latest_attempt.exam_result,
            'exam_date':    latest_attempt.exam_date,
            'all_attempts': [
                {
                    'module_name': a.student_module.module.module_name,
                    'attempt_number': a.attempt_number,
                    'exam_date': a.exam_date.strftime('%d %b %Y'),
                    'score': a.score,
                    'threshold': a.pass_threshold,
                    'passed': a.exam_result,
                }
                for a in student_attempts
            ],
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
        },
        'student_rows': student_rows,
        'modules_needing_attention': modules_needing_attention,
        'campus_pass_rates': campus_pass_rates,
        'campus_comparison': campus_comparison,
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

    # The prefetch is what makes every `.is_evaluated`/`.is_competent`
    # check below O(1) instead of 2+ extra queries per student — this
    # view used to issue ~200 queries for 40 students before it was
    # added (see Student.is_evaluated's docstring for why).
    students = Student.objects.select_related('applicant', 'applicant__program').prefetch_related(
        Prefetch(
            'student_modules',
            queryset=StudentModule.objects.select_related('module', 'local_assessment'),
        )
    )
    total_students = students.count()

    programs = Program.objects.filter(is_active=True)
    program_rows = []
    for program in programs:
        program_students = students.filter(applicant__program=program)
        competent = sum(1 for s in program_students if s.is_competent)
        evaluated = sum(1 for s in program_students if s.is_evaluated)
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

    evaluated_students = [s for s in students if s.is_evaluated]
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
