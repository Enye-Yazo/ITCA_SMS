# admissions/views/applications.py
"""
The application/registration multi-step form workflow, plus the Exec
Admin review pipeline (list → detail → approve/reject) for applications
already submitted. `application_step` also doubles as the entry point
for historical onboarding (see its `historical` kwarg) — the actual
"skip the review, assign straight to a class" finishing step for that
flow lives in `onboarding.py` since it's a distinct action with its own
permission and capacity checks, not a form step.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from ..models import Applicant, Student
from ..forms import (
    PersonalDetailsForm, ContactAddressForm,
    EducationDisabilityForm, NextOfKinForm
)
from academics.models import Class, Enrollment


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
def application_step(request, step=1, applicant_id=None, historical=False):
    """
    Multi-step application form.
    Handles both new applications (no applicant_id)
    and continuing a draft (applicant_id provided).
    Steps 1-4 are forms. Step 5 is a read-only review.

    `historical=True` is only ever passed by the onboard_new URL — it
    marks a brand-new Applicant (at step 1) as historical onboarding
    rather than a fresh admission, which changes what step 5 offers
    (assign directly to an existing class, vs submit for Exec Admin
    review). Once the Applicant exists, the flag lives on the row
    itself (is_historical_onboarding), so later steps read it from
    there rather than needing it passed through the URL again.
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

        available_classes = None
        if applicant.is_historical_onboarding:
            # Any active class in the applicant's program/campus — unlike
            # a fresh admission, an existing student may belong to any
            # cohort or academic year, not just the current year's New
            # intake, so there's no single "the" active class to assume.
            available_classes = Class.objects.filter(
                program=applicant.program,
                campus=applicant.campus,
                is_active=True,
            ).select_related('trainer').order_by('-academic_year', 'cohort')

        context = {
            'applicant': applicant,
            'contact': contact,
            'step': step,
            'total_steps': TOTAL_STEPS,
            'steps': STEPS,
            'available_classes': available_classes,
            'is_historical_onboarding': applicant.is_historical_onboarding,
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
                # Save applicant as draft on step 1. `historical` only
                # matters the first time this applicant is created —
                # re-editing step 1 of an existing draft must not flip
                # the flag back to False for a URL that no longer
                # carries it.
                is_new_applicant = applicant is None
                applicant = form.save(commit=False)
                applicant.application_status = Applicant.ApplicationStatus.DRAFT
                if is_new_applicant:
                    applicant.is_historical_onboarding = historical
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
        # For a brand-new draft, is_historical_onboarding isn't set on the
        # (not-yet-created) applicant yet — fall back to the URL's own
        # `historical` kwarg so step 1's very first GET still shows the
        # onboarding banner.
        'is_historical_onboarding': applicant.is_historical_onboarding if applicant else historical,
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

    # Near-miss classes — any class that exists for this program/campus but
    # doesn't qualify (wrong year, wrong cohort, or inactive) — so the "no
    # active class" banner shows *why* an existing class doesn't count,
    # rather than leaving an Exec Admin who's already created a class
    # wondering why approval is still blocked.
    near_miss_classes = None
    if not active_class:
        near_miss_classes = Class.objects.filter(
            program=applicant.program, campus=applicant.campus
        ).exclude(
            academic_year=current_year, cohort=Class.CohortChoices.NEW, is_active=True
        ).order_by('-academic_year')

    context = {
        'applicant': applicant,
        'contact': contact,
        'active_class': active_class,
        'remaining_capacity': remaining_capacity,
        'near_miss_classes': near_miss_classes,
        'current_year': current_year,
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

    # Block if the class has no trainer assigned, or its "trainer" isn't
    # actually a Trainer-role account — a student's trainer comes
    # directly from the class below, and there is no fallback trainer.
    # An Exec Admin is never used as one, even implicitly, even if one
    # was set on the class some other way (e.g. Django admin).
    if not active_class.trainer_id or not active_class.trainer.is_trainer:
        messages.error(
            request,
            f"{active_class} has no trainer assigned. "
            f"Assign a trainer to this class in Settings before approving."
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
    Finalises a draft application and sends it for Exec Admin review —
    moves application_status from Draft to Pending, once every required
    field is confirmed complete. Before this, a Data Capturer's
    in-progress application stays Draft and never shows up as "Pending"
    on the Exec Admin side (dashboard/application_list both filter on
    PENDING specifically) — this used to set status to Pending as early
    as step 1, so an application the Data Capturer hadn't even finished
    filling in yet already looked like something awaiting Exec Admin
    review.
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

    # Actually transition Draft -> Pending, and mark the submission date.
    applicant.application_status = Applicant.ApplicationStatus.PENDING
    applicant.status_date = timezone.now().date()
    applicant.save()

    messages.success(
        request,
        f"Application {applicant.application_reference} submitted for review."
    )

    return redirect('admissions:application_list')
