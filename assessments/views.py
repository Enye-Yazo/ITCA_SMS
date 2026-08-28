# assessments/views.py

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import StudentModule, LocalAssessment, InternationalExamAttempt, Promotion
from .forms import InternationalExamAttemptForm, PromotionRequestForm
from academics.models import Enrollment, Class


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

    context = {
        'attempts': attempts,
        'modules': modules,
        'filters': {'module': module_filter, 'result': result_filter},
    }
    return render(request, 'assessments/exam_attempt_list.html', context)


@login_required
@test_admin_only
def exam_attempt_record(request):
    """
    Records a new international exam attempt for a student's module.
    The attempt number is computed automatically — sequential per
    student+module — never entered by hand.
    """
    if request.method == 'POST':
        form = InternationalExamAttemptForm(request.POST)
        if form.is_valid():
            attempt = form.save(commit=False)
            existing_attempts = InternationalExamAttempt.objects.filter(
                student_module=attempt.student_module
            ).count()
            attempt.attempt_number = existing_attempts + 1
            attempt.save()

            messages.success(
                request,
                f"Recorded attempt {attempt.attempt_number} for "
                f"{attempt.student_module.student.full_name} — "
                f"{attempt.student_module.module.module_code}."
            )
            return redirect('assessments:exam_attempt_list')
    else:
        form = InternationalExamAttemptForm()

    return render(request, 'assessments/exam_attempt_form.html', {'form': form})


# ─── Promotion Workflow ──────────────────────────────────────────────────────
@login_required
@trainer_only
def promotion_request(request, enrollment_id):
    """
    A Trainer requests promoting one of their own students from their
    current (New) enrollment to a Returning class.
    Only offers Returning classes in the same program and campus —
    the trainer cannot promote a student into an unrelated program.
    """
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student', 'class_group'),
        pk=enrollment_id
    )

    if enrollment.student.trainer_id != request.user.id:
        messages.error(request, "You may only request promotions for your own students.")
        return redirect('assessments:grading_index')

    if enrollment.status != Enrollment.EnrollmentStatus.ACTIVE:
        messages.error(request, "Only students with an active enrollment can be promoted.")
        return redirect('assessments:grading_index')

    if enrollment.promotion_requests.filter(
        status=Promotion.PromotionStatus.PENDING
    ).exists():
        messages.error(request, "A promotion request is already pending for this student.")
        return redirect('assessments:promotion_list')

    if request.method == 'POST':
        form = PromotionRequestForm(request.POST)
        if form.is_valid():
            promotion = form.save(commit=False)
            promotion.current_enrollment = enrollment
            promotion.requested_by = request.user
            promotion.save()
            messages.success(
                request,
                f"Promotion request submitted for {enrollment.student.full_name}."
            )
            return redirect('assessments:promotion_list')
    else:
        form = PromotionRequestForm()

    # Restrict target class choices to Returning classes in the same
    # program and campus as the student's current class.
    form.fields['target_class'].queryset = Class.objects.filter(
        program=enrollment.class_group.program,
        campus=enrollment.class_group.campus,
        cohort=Class.CohortChoices.RETURNING,
        is_active=True,
    ).exclude(pk=enrollment.class_group_id)

    return render(request, 'assessments/promotion_request.html', {
        'form': form,
        'enrollment': enrollment,
    })


@login_required
def promotion_list(request):
    """
    Trainers see their own promotion requests and history.
    Exec Admins see every request, with pending ones actionable.
    """
    if not (request.user.is_trainer or request.user.is_exec_admin):
        messages.error(request, "You do not have permission to view promotions.")
        return redirect('dashboard:index')

    promotions = Promotion.objects.select_related(
        'current_enrollment__student', 'current_enrollment__student__applicant',
        'current_enrollment__class_group', 'target_class',
        'requested_by', 'reviewed_by',
    ).order_by('-request_date')

    if request.user.is_trainer:
        promotions = promotions.filter(requested_by=request.user)

    return render(request, 'assessments/promotion_list.html', {'promotions': promotions})


@login_required
@require_POST
@transaction.atomic
def promotion_approve(request, promotion_id):
    """
    Approves a promotion: marks the current enrollment Promoted and
    creates a new Active enrollment in the target class.
    """
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can approve promotions.")
        return redirect('dashboard:index')

    promotion = get_object_or_404(
        Promotion.objects.select_related('current_enrollment', 'target_class'),
        pk=promotion_id
    )

    if promotion.status != Promotion.PromotionStatus.PENDING:
        messages.error(request, "This promotion request has already been reviewed.")
        return redirect('assessments:promotion_list')

    promotion.current_enrollment.status = Enrollment.EnrollmentStatus.PROMOTED
    promotion.current_enrollment.end_date = timezone.now().date()
    promotion.current_enrollment.save()

    Enrollment.objects.create(
        student=promotion.current_enrollment.student,
        class_group=promotion.target_class,
        start_date=timezone.now().date(),
        status=Enrollment.EnrollmentStatus.ACTIVE,
    )

    promotion.status = Promotion.PromotionStatus.APPROVED
    promotion.reviewed_by = request.user
    promotion.review_date = timezone.now().date()
    promotion.save()

    messages.success(
        request,
        f"{promotion.current_enrollment.student.full_name} promoted to "
        f"{promotion.target_class}."
    )
    return redirect('assessments:promotion_list')


@login_required
@require_POST
def promotion_reject(request, promotion_id):
    """Rejects a promotion request. The student's current enrollment is untouched."""
    if not request.user.is_exec_admin:
        messages.error(request, "Only Exec Admins can reject promotions.")
        return redirect('dashboard:index')

    promotion = get_object_or_404(Promotion, pk=promotion_id)

    if promotion.status != Promotion.PromotionStatus.PENDING:
        messages.error(request, "This promotion request has already been reviewed.")
        return redirect('assessments:promotion_list')

    promotion.status = Promotion.PromotionStatus.REJECTED
    promotion.reviewed_by = request.user
    promotion.review_date = timezone.now().date()
    promotion.save()

    messages.warning(request, "Promotion request rejected.")
    return redirect('assessments:promotion_list')
