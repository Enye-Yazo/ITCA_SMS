# admissions/views/alumni.py
"""
The Alumni list — every graduated student, with the pass-rate/graduation
stats shown at the top of that page.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from ..models import Alumni
from academics.models import Campus, Program
from assessments.models import InternationalExamAttempt


@login_required
def alumni_list(request):
    """
    Every graduated student, grouped into two sections: those who
    graduated on NQF5 alone (no international certification passed),
    and those who also passed at least one international certification
    — Alumni.objects is populated automatically by
    assessments.models.auto_graduate_on_full_nqf5_pass the moment a
    Returning-cohort student passes every assigned NQF5 module, and
    passing an Int Cert was never a graduation requirement (a student
    can keep resitting a failed one indefinitely), so this grouping is
    purely informational, not a completeness indicator.

    Filterable by campus, program and graduation year.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can view Alumni.")
        return redirect('dashboard:index')

    alumni = Alumni.objects.select_related(
        'student', 'student__applicant', 'program', 'campus'
    ).order_by('-graduation_date')

    campus_id = request.GET.get('campus', 'all')
    program_id = request.GET.get('program', 'all')
    year = request.GET.get('year', 'all')
    search = request.GET.get('q', '').strip()

    if campus_id != 'all':
        alumni = alumni.filter(campus_id=campus_id)
    if program_id != 'all':
        alumni = alumni.filter(program_id=program_id)
    if year != 'all':
        alumni = alumni.filter(graduation_date__year=year)
    if search:
        alumni = alumni.filter(
            Q(student__applicant__first_name__icontains=search) |
            Q(student__applicant__last_name__icontains=search) |
            Q(student__student_id_code__icontains=search)
        )

    graduation_years = Alumni.objects.dates('graduation_date', 'year', order='DESC')

    # Materialize once — iterated more than once below (grouping certs,
    # then building the two row lists), and a queryset re-evaluates its
    # SQL on every fresh iteration unless the result is cached like this.
    alumni = list(alumni)

    # One query for every passed attempt across every alumnus's student,
    # grouped in Python by student id — replaces what used to be a
    # fresh InternationalExamAttempt query *per alumnus in the loop
    # below* (a textbook N+1).
    passed_certs_by_student_id = {}
    for module_name, student_id in (
        InternationalExamAttempt.objects
        .filter(student_module__student_id__in=[record.student_id for record in alumni], exam_result=True)
        .values_list('student_module__module__module_name', 'student_module__student_id')
        .distinct()
    ):
        passed_certs_by_student_id.setdefault(student_id, []).append(module_name)

    nqf5_only_rows = []
    certified_rows = []
    total_certs_passed = 0
    for record in alumni:
        passed_certs = passed_certs_by_student_id.get(record.student_id, [])
        total_certs_passed += len(passed_certs)

        row = {'alumni': record, 'passed_certs': passed_certs}
        if passed_certs:
            certified_rows.append(row)
        else:
            nqf5_only_rows.append(row)

    total_alumni = len(nqf5_only_rows) + len(certified_rows)
    current_year = timezone.now().year
    graduated_this_year = sum(
        1 for row in nqf5_only_rows + certified_rows
        if row['alumni'].graduation_date.year == current_year
    )
    avg_certs_passed = round(total_certs_passed / total_alumni, 1) if total_alumni else 0

    context = {
        'nqf5_only_rows': nqf5_only_rows,
        'certified_rows': certified_rows,
        'campuses': Campus.objects.filter(is_active=True),
        'programs': Program.objects.filter(is_active=True),
        'graduation_years': [d.year for d in graduation_years],
        'filters': {'campus': campus_id, 'program': program_id, 'year': year, 'q': search},
        'current_year': current_year,
        'stats': {
            'total_alumni': total_alumni,
            'graduated_this_year': graduated_this_year,
            'avg_certs_passed': avg_certs_passed,
        },
    }
    return render(request, 'admissions/alumni_list.html', context)
