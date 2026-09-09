# admissions/views/onboarding.py
"""
The finishing step of the historical-onboarding flow. The form steps
themselves (1-4, plus the step-5 review page) are shared with a normal
application via `applications.application_step` — this module only
holds the one action that's genuinely distinct to onboarding: placing an
already-real, already-enrolled student straight into a class, with no
Exec Admin admission decision to make since there isn't one for someone
who already exists.
"""

from datetime import datetime

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from ..models import Applicant, Student
from academics.models import Class, Enrollment


@login_required
@transaction.atomic
def onboard_confirm(request, applicant_id):
    """
    Finishes the historical-onboarding flow (see application_step's
    `historical` kwarg): places an already-real, already-enrolled
    student straight into the class the Data Capturer picked at step 5
    — no separate Exec Admin admission decision, since there isn't one
    to make for a student who already exists. Still enforces class
    capacity, same as a normal approval.
    """
    if not (request.user.is_data_capturer or request.user.is_exec_admin):
        messages.error(request, "You do not have permission to onboard students.")
        return redirect('dashboard:index')

    applicant = get_object_or_404(Applicant, pk=applicant_id)

    if not applicant.is_historical_onboarding:
        messages.error(request, "This application isn't a historical onboarding record.")
        return redirect('admissions:application_step', applicant_id=applicant_id, step=5)

    if hasattr(applicant, 'student_profile'):
        messages.info(request, f"{applicant.full_name} has already been onboarded.")
        return redirect('admissions:student_detail', student_id=applicant.student_profile.id)

    if request.method != 'POST':
        return redirect('admissions:application_step', applicant_id=applicant_id, step=5)

    target_class = get_object_or_404(
        Class, pk=request.POST.get('class_id'),
        program=applicant.program, campus=applicant.campus,
    )

    enrolled_count = Enrollment.objects.filter(
        class_group=target_class, status=Enrollment.EnrollmentStatus.ACTIVE
    ).count()
    if enrolled_count >= target_class.capacity:
        messages.error(
            request,
            f"{target_class} is at capacity ({target_class.capacity} students). "
            f"Increase capacity or pick a different class."
        )
        return redirect('admissions:application_step', applicant_id=applicant_id, step=5)

    try:
        # Submitted as dd/mm/yyyy by the flatpickr-driven text input
        # (templates/admissions/step_5_review.html), not the native
        # <input type="date">'s always-ISO value.
        start_date = datetime.strptime(request.POST.get('start_date', ''), '%d/%m/%Y').date()
    except ValueError:
        start_date = timezone.now().date()

    # Creating the Student triggers the same default-module-assignment
    # signal a fresh approval does, so the student's local assessment
    # slots exist immediately for the Trainer to backfill marks into.
    student = Student.objects.create(applicant=applicant, trainer=target_class.trainer)
    Enrollment.objects.create(
        student=student, class_group=target_class,
        start_date=start_date, status=Enrollment.EnrollmentStatus.ACTIVE,
    )

    applicant.application_status = Applicant.ApplicationStatus.APPROVED
    applicant.status_date = timezone.now().date()
    applicant.save()

    messages.success(
        request,
        f"{applicant.full_name} onboarded as {student.student_id_code}."
    )
    return redirect('admissions:student_detail', student_id=student.id)
