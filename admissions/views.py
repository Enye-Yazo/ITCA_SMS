# admissions/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from .models import Applicant, StudentContact, Student, Alumni
from .forms import (
    PersonalDetailsForm, ContactAddressForm,
    EducationDisabilityForm, NextOfKinForm
)
from academics.models import Campus, Program, Class, Enrollment
from accounts.models import SystemUser, UserRole
from assessments.models import Promotion, StudentModule, InternationalExamAttempt


# ─── Step configuration ───────────────────────────────────────────────────────
# Maps step number to (form class, template, step label)
STEPS = {
    1: (PersonalDetailsForm,      'admissions/step_1_personal.html',   'Personal details'),
    2: (ContactAddressForm,       'admissions/step_2_contact.html',    'Contact & address'),
    3: (EducationDisabilityForm,  'admissions/step_3_education.html',  'Education & disability'),
    4: (NextOfKinForm,            'admissions/step_4_next_of_kin.html','Next of kin'),
    5: (None,                     'admissions/step_5_review.html',     'Review & submit'),
}

TOTAL_STEPS = len(STEPS)


@login_required
def application_step(request, step=1, applicant_id=None):
    """
    Multi-step application form.
    Handles both new applications (no applicant_id)
    and continuing a draft (applicant_id provided).
    Steps 1-4 are forms. Step 5 is a read-only review.
    """

    # Only Data Capturers and Exec Admins can create applications
    if not (request.user.is_data_capturer or request.user.is_exec_admin):
        messages.error(request, "You do not have permission to create applications.")
        return redirect('dashboard:index')

    # Load existing applicant if editing a draft
    applicant = None
    if applicant_id:
        applicant = get_object_or_404(Applicant, pk=applicant_id)

    form_class, template, step_label = STEPS[step]
    duplicate_applicant = None
    form = None

    # ── Step 5: Review (no form, read-only) ───────────────────────────────────
    if step == 5:
        if not applicant:
            return redirect('admissions:application_new')

        # Load the next of kin for review
        contact = applicant.contacts.first()

        context = {
            'applicant': applicant,
            'contact': contact,
            'step': step,
            'total_steps': TOTAL_STEPS,
            'steps': STEPS,
        }
        return render(request, template, context)

    # ── Steps 1-4: Form steps ─────────────────────────────────────────────────
    if request.method == 'POST':
        # Step 4 form operates on StudentContact, not Applicant
        if step == 4:
            contact = applicant.contacts.first() if applicant else None
            form = form_class(request.POST, instance=contact)
        else:
            form = form_class(request.POST, instance=applicant)

        if form.is_valid():
            if step == 1:
                # Save applicant as draft on step 1
                applicant = form.save(commit=False)
                applicant.application_status = Applicant.ApplicationStatus.PENDING
                applicant.save()

            elif step == 4:
                # Save next of kin linked to the applicant
                contact = form.save(commit=False)
                contact.applicant = applicant
                contact.save()

            else:
                # Steps 2 and 3 update the existing applicant
                form.save()

            # Advance to next step
            next_step = step + 1
            return redirect(
                'admissions:application_step',
                applicant_id=applicant.pk,
                step=next_step
            )

        else:
            # Check if the error is a duplicate ID number
            id_errors = form.errors.get('id_number', [])
            for error in id_errors:
                if error.startswith('DUPLICATE:'):
                    # Parse the duplicate info from the error message
                    # Format: DUPLICATE:<pk>:<reference>
                    parts = error.split(':')
                    duplicate_pk = parts[1]
                    duplicate_applicant = get_object_or_404(
                        Applicant, pk=duplicate_pk
                    )
                    # Clear the raw error so it doesn't show as a field error
                    form.errors['id_number'] = []

    else:
        # GET request — initialise the form with existing data if editing
        if step == 4 and applicant:
            contact = applicant.contacts.first()
            form = form_class(instance=contact)
        else:
            form = form_class(instance=applicant)

    context = {
        'form': form,
        'applicant': applicant,
        'step': step,
        'total_steps': TOTAL_STEPS,
        'steps': STEPS,
        'duplicate_applicant': duplicate_applicant,
    }

    return render(request, template, context)


@login_required
def application_list(request):
    """
    Lists all applications.
    Exec Admin sees all. Data Capturers see all (to prevent duplicates).
    Filterable by status.
    """
    if not (request.user.is_exec_admin or request.user.is_data_capturer):
        return redirect('dashboard:index')

    status_filter = request.GET.get('status', 'Pending')

    applications = Applicant.objects.select_related(
        'campus', 'program'
    ).order_by('-date_applied')

    if status_filter != 'all':
        applications = applications.filter(application_status=status_filter)

    context = {
        'applications': applications,
        'status_filter': status_filter,
        'status_choices': Applicant.ApplicationStatus.choices,
    }

    return render(request, 'admissions/application_list.html', context)


@login_required
def application_detail(request, applicant_id):
    """
    Read-only view of a single application for the Exec Admin.
    Shows full applicant details, next of kin, and approval actions.
    Also shows remaining class capacity.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can review applications.")
        return redirect('dashboard:index')

    applicant = get_object_or_404(
        Applicant.objects.select_related('campus', 'program'),
        pk=applicant_id
    )
    contact = applicant.contacts.first()

    # Find the active class for this applicant's program and campus
    current_year = timezone.now().year
    active_class = Class.objects.filter(
        program=applicant.program,
        campus=applicant.campus,
        academic_year=current_year,
        is_active=True,
        cohort=Class.CohortChoices.NEW
    ).first()

    # Calculate remaining capacity
    remaining_capacity = None
    if active_class:
        enrolled_count = Enrollment.objects.filter(
            class_group=active_class,
            status=Enrollment.EnrollmentStatus.ACTIVE
        ).count()
        remaining_capacity = active_class.capacity - enrolled_count

    context = {
        'applicant': applicant,
        'contact': contact,
        'active_class': active_class,
        'remaining_capacity': remaining_capacity,
    }

    return render(request, 'admissions/application_detail.html', context)


@login_required
@transaction.atomic
def application_approve(request, applicant_id):
    """
    Approves an application and registers the applicant as a student.
    Automatically assigns them to the active class.
    Blocks approval if no active class exists or class is at capacity.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can approve applications.")
        return redirect('dashboard:index')

    if request.method != 'POST':
        return redirect('admissions:application_detail', applicant_id=applicant_id)

    applicant = get_object_or_404(Applicant, pk=applicant_id)

    # Find active class
    current_year = timezone.now().year
    active_class = Class.objects.filter(
        program=applicant.program,
        campus=applicant.campus,
        academic_year=current_year,
        is_active=True,
        cohort=Class.CohortChoices.NEW
    ).first()

    # Block if no class exists
    if not active_class:
        messages.error(
            request,
            f"No active class found for {applicant.program.program_name} "
            f"at {applicant.campus.campus_name} for {current_year}. "
            f"Create a class first before approving."
        )
        return redirect('admissions:application_detail', applicant_id=applicant_id)

    # Block if class is at capacity
    enrolled_count = Enrollment.objects.filter(
        class_group=active_class,
        status=Enrollment.EnrollmentStatus.ACTIVE
    ).count()

    if enrolled_count >= active_class.capacity:
        messages.error(
            request,
            f"This class is at capacity ({active_class.capacity} students). "
            f"Increase the class capacity or create a new class before approving."
        )
        return redirect('admissions:application_detail', applicant_id=applicant_id)

    # ── All checks passed — create the student record ─────────────────────────

    # Create Student — this triggers the signal that assigns default modules
    student = Student.objects.create(
        applicant=applicant,
        trainer=active_class.trainer,
    )

    # Enroll the student in the active class
    Enrollment.objects.create(
        student=student,
        class_group=active_class,
        start_date=timezone.now().date(),
        status=Enrollment.EnrollmentStatus.ACTIVE
    )

    # Update applicant status
    applicant.application_status = Applicant.ApplicationStatus.APPROVED
    applicant.status_date = timezone.now().date()
    applicant.save()

    messages.success(
        request,
        f"{applicant.full_name} has been approved and registered as a student. "
        f"Reference: {applicant.application_reference}"
    )

    return redirect('admissions:application_list')


@login_required
def application_reject(request, applicant_id):
    """
    Rejects an application.
    Rejection reason is fixed: campus capacity reached.
    Record is retained for one year per SRD requirement 10.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can reject applications.")
        return redirect('dashboard:index')

    if request.method != 'POST':
        return redirect('admissions:application_detail', applicant_id=applicant_id)

    applicant = get_object_or_404(Applicant, pk=applicant_id)
    applicant.application_status = Applicant.ApplicationStatus.REJECTED
    applicant.status_date = timezone.now().date()
    applicant.save()

    messages.warning(
        request,
        f"{applicant.full_name}'s application has been rejected. "
        f"Reason: Campus capacity reached."
    )

    return redirect('admissions:application_list')

@login_required
def application_submit(request, applicant_id):
    """
    Finalises a draft application and sends it for exec admin review.
    Changes status from Pending to Pending (already set) and confirms
    the application is complete and ready for review.
    """
    if not (request.user.is_data_capturer or request.user.is_exec_admin):
        return redirect('dashboard:index')

    if request.method != 'POST':
        return redirect('admissions:application_step',
                       applicant_id=applicant_id, step=5)

    applicant = get_object_or_404(Applicant, pk=applicant_id)

    # Confirm all required fields are complete before submitting
    missing = []
    if not applicant.personal_email:
        missing.append("contact details")
    if not applicant.school_name:
        missing.append("education details")
    if not applicant.contacts.exists():
        missing.append("next of kin")

    if missing:
        messages.error(
            request,
            f"Application is incomplete. Missing: {', '.join(missing)}."
        )
        return redirect('admissions:application_step',
                       applicant_id=applicant_id, step=5)

    # Mark the submission date
    applicant.status_date = timezone.now().date()
    applicant.save()

    messages.success(
        request,
        f"Application {applicant.application_reference} submitted for review."
    )

    return redirect('admissions:application_list')


# ─── Student List ─────────────────────────────────────────────────────────────
def _filtered_student_rows(request):
    """
    Shared filtering logic for the student list page and the Excel export,
    so the two always agree on which students match the current filters.
    Exec Admin sees every student. Trainers see only their own.
    Returns a list of {'student': Student, 'cohort': str, 'enrollment': Enrollment|None}.
    """
    students = Student.objects.select_related(
        'applicant', 'applicant__campus', 'applicant__program', 'trainer'
    ).prefetch_related('enrollments__class_group')

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
        students = students.filter(student_id_code__icontains=search)

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
    Lists all registered students.
    Filterable by campus, cohort, program and (for Exec Admin) trainer,
    and searchable by student ID.
    """
    if not (request.user.is_exec_admin or request.user.is_trainer):
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
        "Formative Average (%)", "Competent",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        student = row['student']
        enrollment = row['enrollment']
        formative_average = student.formative_average

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
            round(formative_average, 1) if formative_average is not None else '',
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
    Full academic history for a single student:
    modules, local assessments, international exam attempts,
    enrollments and promotion history.
    Exec Admin can view any student; a Trainer only their own.
    """
    if not (request.user.is_exec_admin or request.user.is_trainer):
        messages.error(request, "You do not have permission to view students.")
        return redirect('dashboard:index')

    student = get_object_or_404(
        Student.objects.select_related('applicant', 'applicant__campus', 'applicant__program', 'trainer'),
        pk=student_id
    )

    if request.user.is_trainer and student.trainer_id != request.user.id:
        messages.error(request, "You may only view your own students.")
        return redirect('admissions:student_list')

    student_modules = StudentModule.objects.select_related('module').prefetch_related(
        'local_assessments', 'exam_attempts'
    ).filter(student=student)

    enrollments = student.enrollments.select_related('class_group').order_by('-start_date')
    promotions = Promotion.objects.filter(
        current_enrollment__student=student
    ).select_related('target_class').order_by('-request_date')

    active_enrollment = enrollments.filter(status=Enrollment.EnrollmentStatus.ACTIVE).first()

    context = {
        'student': student,
        'student_modules': student_modules,
        'enrollments': enrollments,
        'promotions': promotions,
        'active_enrollment': active_enrollment,
    }
    return render(request, 'admissions/student_detail.html', context)