# admissions/views/students.py
"""
The Student List/Detail/Export views, plus the smaller student-profile
actions (setting an email, adding a module, deleting a student). These
all operate on an already-registered `Student`, as distinct from the
`applications.py` pipeline that gets an Applicant to that point.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Prefetch, Q
from django.views.decorators.http import require_POST

from ..models import Student, Alumni
from academics.models import Campus, Program, Module, Class, Enrollment
from accounts.models import SystemUser, UserRole
from assessments.models import StudentModule, InternationalExamAttempt


# ─── Student List ─────────────────────────────────────────────────────────────
def _filtered_student_rows(request):
    """
    Shared filtering logic for the student list page and the Excel export,
    so the two always agree on which students match the current filters.
    Exec Admin sees every student. Trainers see only their own.
    Returns a list of {'student': Student, 'cohort': str, 'enrollment': Enrollment|None}.
    """
    # The student_modules Prefetch only actually matters for the Excel
    # export (student.is_competent, checked per row there) — added here
    # rather than in student_export specifically so this shared function
    # stays the single source of truth for both. One extra query
    # regardless of row count; negligible on the plain student list too.
    students = Student.objects.select_related(
        'applicant', 'applicant__campus', 'applicant__program', 'trainer'
    ).prefetch_related(
        'enrollments__class_group',
        Prefetch(
            'student_modules',
            queryset=StudentModule.objects.select_related('module', 'local_assessment'),
        ),
    )

    if request.user.is_trainer:
        students = students.filter(trainer=request.user)

    campus_id = request.GET.get('campus', 'all')
    program_id = request.GET.get('program', 'all')
    cohort = request.GET.get('cohort', 'all')
    trainer_id = request.GET.get('trainer', 'all')
    search = request.GET.get('q', '').strip()

    if campus_id != 'all':
        students = students.filter(applicant__campus_id=campus_id)
    if program_id != 'all':
        students = students.filter(applicant__program_id=program_id)
    if trainer_id != 'all' and request.user.is_exec_admin:
        students = students.filter(trainer_id=trainer_id)
    if search:
        students = students.filter(
            Q(student_id_code__icontains=search) |
            Q(applicant__first_name__icontains=search) |
            Q(applicant__last_name__icontains=search)
        )

    # Cohort lives on the student's most recent enrollment, so filter in Python
    # once the queryset above has already narrowed things down.
    rows = []
    for student in students:
        latest_enrollment = None
        for enrollment in student.enrollments.all():
            if latest_enrollment is None or enrollment.start_date > latest_enrollment.start_date:
                latest_enrollment = enrollment
        student_cohort = latest_enrollment.class_group.cohort if latest_enrollment else None

        if cohort != 'all' and student_cohort != cohort:
            continue

        rows.append({
            'student': student,
            'cohort': student_cohort or '—',
            'enrollment': latest_enrollment,
        })

    return rows


@login_required
def student_list(request):
    """
    Lists all registered students, including their demographic details
    (ID number, date of birth, address, disability status, etc. — see
    student_detail). Exec Admin and Test Admin only.

    Trainers previously had access to this via the "Students" nav link,
    which unintentionally exposed every one of their students'
    demographic information — Trainers now only get "My Students"
    (assessments:grading_index), which shows names, IDs and NQF5
    ratings, nothing demographic. Test Admin needs it to look up a
    student before creating their external vendor platform profiles
    (Microsoft Learn, CompTIA, etc. — see Platform Management).
    """
    if not (request.user.is_exec_admin or request.user.is_test_admin):
        messages.error(request, "You do not have permission to view students.")
        return redirect('dashboard:index')

    campus_id = request.GET.get('campus', 'all')
    program_id = request.GET.get('program', 'all')
    cohort = request.GET.get('cohort', 'all')
    trainer_id = request.GET.get('trainer', 'all')
    search = request.GET.get('q', '').strip()

    context = {
        'rows': _filtered_student_rows(request),
        'campuses': Campus.objects.filter(is_active=True),
        'programs': Program.objects.filter(is_active=True),
        'cohort_choices': Class.CohortChoices.choices,
        'trainers': SystemUser.objects.filter(role=UserRole.TRAINER, is_active=True) if request.user.is_exec_admin else None,
        'filters': {
            'campus': campus_id,
            'program': program_id,
            'cohort': cohort,
            'trainer': trainer_id,
            'q': search,
        },
    }
    return render(request, 'admissions/student_list.html', context)


# ─── Student Excel Export ─────────────────────────────────────────────────────
@login_required
def student_export(request):
    """
    Exports the currently filtered student list to .xlsx.
    Exec Admin only. Deliberately excludes LearningPlatformCredential and
    AccessKey fields (username/password/key values) per SRD requirement 12 —
    only academic and contact data is included.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can export student data.")
        return redirect('dashboard:index')

    import openpyxl
    from openpyxl.styles import Font
    from django.http import HttpResponse

    rows = _filtered_student_rows(request)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Students"

    headers = [
        "Student ID", "Full Name", "Campus", "Program", "Cohort",
        "Trainer", "Enrollment Status", "Enrollment Start Date",
        "ID Number", "Personal Email", "Student Email", "Phone",
        "NQF5 Competent",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        student = row['student']
        enrollment = row['enrollment']

        sheet.append([
            student.student_id_code,
            student.full_name,
            student.campus.campus_name,
            student.program.program_name,
            row['cohort'],
            student.trainer.full_name if student.trainer else '',
            enrollment.status if enrollment else '',
            enrollment.start_date.isoformat() if enrollment else '',
            student.applicant.id_number,
            student.applicant.personal_email or '',
            student.student_email or '',
            student.applicant.phone or '',
            'Yes' if student.is_competent else 'No',
        ])

    for column_cells in sheet.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 40)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"itca_students_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    workbook.save(response)
    return response


# ─── Student Detail ───────────────────────────────────────────────────────────
@login_required
def student_detail(request, student_id):
    """
    Full academic history for a single student: demographic details,
    modules, local assessments, international exam attempts,
    and enrollment history (a Promoted row followed by a new Active
    enrollment in the enrollment list below is that student's
    promotion history — promotion is now automatic, not a separate
    workflow, so there's nothing else to show).

    Exec Admin and Test Admin only. Trainers used to be able to reach
    this (their own students only) via the "Students" nav link, which
    unintentionally exposed demographic details (ID number, DOB,
    address, disability status, etc.) they have no business reason to
    see; "My Students" (assessments:grading_index) is their view now.
    Test Admin needs it to create a student's external vendor platform
    profiles (Microsoft Learn, CompTIA, etc.).
    """
    if not (request.user.is_exec_admin or request.user.is_test_admin):
        messages.error(request, "You do not have permission to view students.")
        return redirect('dashboard:index')

    student = get_object_or_404(
        Student.objects.select_related('applicant', 'applicant__campus', 'applicant__program', 'trainer'),
        pk=student_id
    )

    student_modules = StudentModule.objects.select_related(
        'module', 'local_assessment'
    ).prefetch_related('exam_attempts').filter(student=student)

    enrollments = student.enrollments.select_related('class_group').order_by('-start_date')

    active_enrollment = enrollments.filter(status=Enrollment.EnrollmentStatus.ACTIVE).first()

    # For the "+ Add module" control — only modules not already in the
    # student's package are worth offering.
    available_modules = Module.objects.filter(is_active=True).exclude(
        id__in=student_modules.values_list('module_id', flat=True)
    ).order_by('module_code')

    context = {
        'student': student,
        'student_modules': student_modules,
        'available_modules': available_modules,
        'enrollments': enrollments,
        'active_enrollment': active_enrollment,
    }
    return render(request, 'admissions/student_detail.html', context)


@login_required
def student_set_email(request, student_id):
    """
    Sets a student's school-issued email — Test Admin (who owns creating
    student email accounts and vendor platform access) or Exec Admin.
    student_email is unique, so a duplicate is rejected with a clear
    message rather than a raw IntegrityError.

    Called from two places: the Students detail page (Exec Admin), and
    inline from Platform Management's Access Credentials tables (Test
    Admin, when a row's student has no email yet) — `from_platform=1`
    sends the redirect back there instead of student_detail.
    """
    if not (request.user.is_exec_admin or request.user.is_test_admin):
        messages.error(request, "Only Exec Admins and Test Admins can set a student's email address.")
        return redirect('admissions:student_detail', student_id=student_id)

    from_platform = request.POST.get('from_platform') == '1'
    fallback = (
        redirect('assessments:platform_management') if from_platform
        else redirect('admissions:student_detail', student_id=student_id)
    )

    if request.method != 'POST':
        return fallback

    student = get_object_or_404(Student, pk=student_id)
    email = request.POST.get('student_email', '').strip()

    if email and Student.objects.filter(student_email__iexact=email).exclude(pk=student.pk).exists():
        messages.error(request, f"{email} is already assigned to another student.")
        return fallback

    student.student_email = email or None
    student.save(update_fields=['student_email'])
    messages.success(request, "Student email updated.")
    return fallback


# ─── Add a module to a student's package ────────────────────────────────────
@login_required
@require_POST
def student_module_add(request, student_id):
    """
    Lets an Exec Admin add an extra module to a student's package
    directly from their profile — e.g. a Software Development student
    picking up Security+ from Cyber Security. Always an Elective
    assignment (this is a manual add, not a program default), and
    reuses the same get_or_create pattern as recording an exam
    attempt/booking for a module the student isn't formally assigned to
    yet.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can add modules to a student's package.")
        return redirect('admissions:student_detail', student_id=student_id)

    student = get_object_or_404(Student, pk=student_id)
    module = get_object_or_404(Module, pk=request.POST.get('module_id'), is_active=True)

    student_module, created = StudentModule.objects.get_or_create(
        student=student, module=module,
        defaults={'assignment_type': StudentModule.AssignmentType.ELECTIVE},
    )
    if created:
        messages.success(request, f"Added {module.module_code} — {module.module_name} to {student.full_name}'s modules.")
    else:
        messages.error(request, f"{student.full_name} is already assigned {module.module_code}.")
    return redirect('admissions:student_detail', student_id=student_id)


# ─── Delete a student ────────────────────────────────────────────────────────
def _delete_student_and_records(student):
    """
    Deletes a Student and everything that would otherwise PROTECT that
    deletion (Enrollment, StudentModule, the AccessKey/InternationalExamAttempt
    rows hanging off those StudentModules, LearningPlatformCredential,
    Alumni), then the student's own Applicant + StudentContact record —
    a Student is meaningless without one, and Student.applicant is
    itself PROTECTed so the Applicant has to go after the Student, not
    before. LocalAssessment, ExamBooking and PlatformRow all CASCADE
    automatically from StudentModule/Student and need no explicit
    handling here.
    """
    from assessments.models import AccessKey, LearningPlatformCredential

    student_modules = StudentModule.objects.filter(student=student)
    AccessKey.objects.filter(student_module__in=student_modules).delete()
    InternationalExamAttempt.objects.filter(student_module__in=student_modules).delete()
    student_modules.delete()

    LearningPlatformCredential.objects.filter(student=student).delete()
    Alumni.objects.filter(student=student).delete()
    Enrollment.objects.filter(student=student).delete()

    applicant = student.applicant
    student.delete()
    applicant.delete()


@login_required
@require_POST
def student_delete(request, student_id):
    """
    Deletes a student and every record that hangs off them — enrollment
    history, modules, local assessments, exam attempts, platform
    credentials, the lot. Exec Admin only; irreversible, so the template
    gates it behind the themed confirm dialog, not a bare button.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can delete students.")
        return redirect('admissions:student_list')

    student = get_object_or_404(Student, pk=student_id)
    name = student.full_name
    _delete_student_and_records(student)
    messages.success(request, f"Deleted {name} and all their records.")
    return redirect('admissions:student_list')
