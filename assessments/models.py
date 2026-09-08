# assessments/models.py

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.utils import timezone
from admissions.models import Student
from academics.models import ProgramModule


# ─── Student Module ───────────────────────────────────────────────────────────
class StudentModule(models.Model):
    """
    Links a student to a specific module they are studying.
    Acts as the central record for all assessment activity on that module.
    A student can be enrolled in modules from other programs
    e.g. a Software Development student adding Security+ from Cyber Security.
    """

    class ModuleStatus(models.TextChoices):
        IN_PROGRESS = 'In Progress', 'In Progress'
        COMPLETED = 'Completed', 'Completed'
        FAILED = 'Failed', 'Failed'
        WITHDRAWN = 'Withdrawn', 'Withdrawn'

    class AssignmentType(models.TextChoices):
        DEFAULT = 'Default', 'Default'      # Auto-assigned on registration
        ELECTIVE = 'Elective', 'Elective'   # Manually added e.g. cross-program module

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name='student_modules'
    )

    module = models.ForeignKey(
        'academics.Module',
        on_delete=models.PROTECT,
        related_name='student_modules'
    )

    status = models.CharField(
        max_length=20,
        choices=ModuleStatus.choices,
        default=ModuleStatus.IN_PROGRESS
    )

    assignment_type = models.CharField(
        max_length=20,
        choices=AssignmentType.choices,
        default=AssignmentType.DEFAULT,
        help_text="Default = auto-assigned on registration, Elective = manually added"
        )

    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_modules'
        verbose_name = 'Student Module'
        verbose_name_plural = 'Student Modules'
        # A student cannot be enrolled in the same module twice
        unique_together = ['student', 'module']
        ordering = ['student', 'module']

    def __str__(self):
        return f"{self.student.full_name} — {self.module.module_code}"


# ─── Local Assessment ─────────────────────────────────────────────────────────
class LocalAssessment(models.Model):
    """
    Each module has 2 formative assessments (95% pass mark) and
    1 summative assessment (Competent / Not Yet Competent).
    Auto-created when a StudentModule is created.
    Formative marks below 95% can be remediated once — the
    remediation mark becomes final.
    """

    class AssessmentType(models.TextChoices):
        FORMATIVE_1 = 'PFA01', 'Formative 1'
        FORMATIVE_2 = 'PFA02', 'Formative 2'
        SUMMATIVE    = 'PSA',   'Summative'

    student_module = models.ForeignKey(
        StudentModule, on_delete=models.CASCADE,
        related_name='local_assessments'
    )

    assessment_type = models.CharField(
        max_length=10, choices=AssessmentType.choices,
        default=AssessmentType.FORMATIVE_1
    )

    # Formative fields
    mark = models.IntegerField(null=True, blank=True)
    is_remediation = models.BooleanField(default=False)
    remediation_mark = models.IntegerField(null=True, blank=True)

    # Summative field
    competent = models.BooleanField(null=True, blank=True)

    trainer = models.ForeignKey(
        'accounts.SystemUser', on_delete=models.SET_NULL, null=True
    )
    assessment_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'local_assessments'
        verbose_name = 'Local Assessment'
        verbose_name_plural = 'Local Assessments'
        unique_together = ['student_module', 'assessment_type']
        ordering = ['student_module', 'assessment_type']

    def __str__(self):
        return f"{self.student_module} — {self.assessment_type}"

    @property
    def effective_mark(self):
        """The mark that counts toward the student's average."""
        if self.assessment_type == self.AssessmentType.SUMMATIVE:
            return None
        return self.remediation_mark if self.is_remediation else self.mark

    @property
    def passed(self):
        """Whether this formative assessment meets the 95% pass mark."""
        if self.effective_mark is None:
            return None
        return self.effective_mark >= 95


# ─── Signal: auto-create the 3 assessment slots ───────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=StudentModule)
def create_local_assessment_slots(sender, instance, created, **kwargs):
    """
    Fires when a StudentModule is created.
    Creates the 2 formative + 1 summative assessment slots, empty,
    ready for the trainer to fill in marks.
    """
    if not created:
        return

    LocalAssessment.objects.bulk_create([
        LocalAssessment(
            student_module=instance,
            assessment_type=LocalAssessment.AssessmentType.FORMATIVE_1
        ),
        LocalAssessment(
            student_module=instance,
            assessment_type=LocalAssessment.AssessmentType.FORMATIVE_2
        ),
        LocalAssessment(
            student_module=instance,
            assessment_type=LocalAssessment.AssessmentType.SUMMATIVE
        ),
    ])


# ─── International Exam Attempt ───────────────────────────────────────────────
class InternationalExamAttempt(models.Model):
    """
    Records each attempt at an international certification exam.
    Recorded by the Test Admin.
    Multiple attempts are allowed — full history is retained.
    e.g. CompTIA Security+, Microsoft AZ-900
    """
    student_module = models.ForeignKey(
        StudentModule,
        on_delete=models.PROTECT,
        related_name='exam_attempts'
    )

    attempt_number = models.IntegerField(
        help_text="Sequential attempt number e.g. 1 for first attempt, 2 for resit"
    )

    exam_date = models.DateField()

    # Pass or fail
    exam_result = models.BooleanField(
        help_text="True = Passed, False = Failed"
    )

    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text="Score out of 1000 — 700 is the pass mark. Required."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'int_exam_attempts'
        verbose_name = 'International Exam Attempt'
        verbose_name_plural = 'International Exam Attempts'
        ordering = ['student_module', 'attempt_number']
        # Cannot have two attempts with the same number for the same module
        unique_together = ['student_module', 'attempt_number']

    def __str__(self):
        result = "Passed" if self.exam_result else "Failed"
        return (
            f"{self.student_module} — "
            f"Attempt {self.attempt_number} — "
            f"{result}"
        )

    @property
    def percentage_score(self):
        """
        International exams are scored out of 1000 (700 = pass), but Exec
        Admin dashboard calculations and comparisons against local
        assessments are all done on a 0-100 scale — this is the single
        place that conversion happens.
        """
        if self.score is None:
            return None
        return round((self.score / 1000) * 100, 1)


# ─── Access Key ───────────────────────────────────────────────────────────────
class AccessKey(models.Model):
    """
    Stores eBook keys or voucher codes tied to a student's module.
    e.g. a CertMaster access code for a specific CompTIA exam.
    """

    class KeyType(models.TextChoices):
        EBOOK = 'eBook', 'eBook'
        EXAM_VOUCHER = 'Exam Voucher', 'Exam Voucher'
        PLATFORM = 'Platform', 'Platform Access'
        OTHER = 'Other', 'Other'

    student_module = models.ForeignKey(
        StudentModule,
        on_delete=models.PROTECT,
        related_name='access_keys'
    )

    key_type = models.CharField(
        max_length=20,
        choices=KeyType.choices
    )

    key_value = models.CharField(
        max_length=500,
        help_text="The actual key or access code"
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'access_keys'
        verbose_name = 'Access Key'
        verbose_name_plural = 'Access Keys'

    def __str__(self):
        return f"{self.student_module} — {self.key_type}"


# ─── Learning Platform Credential ─────────────────────────────────────────────
class LearningPlatformCredential(models.Model):
    """
    Stores login credentials for external learning platforms.
    e.g. CertMaster, LinkedIn Learning, Microsoft Learn.
    Excluded from all data exports per SRD requirement 12.
    """
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name='platform_credentials'
    )

    platform_name = models.CharField(
        max_length=100,
        help_text="e.g. CertMaster, LinkedIn Learning"
    )

    username = models.CharField(max_length=255)

    # Stored as plain text — discuss encryption with client before go-live
    password = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'learning_platform_credentials'
        verbose_name = 'Learning Platform Credential'
        verbose_name_plural = 'Learning Platform Credentials'

    def __str__(self):
        return f"{self.student.full_name} — {self.platform_name}"


# ─── Signal: automatic promotion on full NQF5 pass ─────────────────────────────
@receiver(post_save, sender=LocalAssessment)
def auto_promote_on_full_nqf5_pass(sender, instance, **kwargs):
    """
    Replaces the old manual Trainer-requests / Exec-Admin-approves
    Promotion workflow: a student is now promoted automatically, the
    moment every local NQF5 assessment they have (both formatives ≥95%
    and the summative marked Competent, across every assigned module)
    is passed.

    Fires on every LocalAssessment save — cheap to over-check since
    `all_nqf5_passed` short-circuits on the first unmet assessment, and
    the enrollment-cohort guard below makes this idempotent: once a
    student is promoted into a Returning class, later saves see a
    non-New active enrollment and no-op immediately.
    """
    from academics.models import Enrollment, Class

    student = instance.student_module.student

    if not student.all_nqf5_passed:
        return

    active_enrollment = Enrollment.objects.filter(
        student=student, status=Enrollment.EnrollmentStatus.ACTIVE
    ).select_related('class_group').first()

    if not active_enrollment or active_enrollment.class_group.cohort != Class.CohortChoices.NEW:
        # No active enrollment to promote from, or already Returning.
        return

    current_year = timezone.now().year
    target_class = Class.objects.filter(
        program=active_enrollment.class_group.program,
        campus=active_enrollment.class_group.campus,
        academic_year=current_year,
        is_active=True,
        cohort=Class.CohortChoices.RETURNING,
    ).first()

    if not target_class:
        # Nothing to promote into yet — an Exec Admin still needs to
        # create the Returning class. The student stays in their
        # current enrollment; this signal fires again on the next
        # grade edit and will pick the class up once it exists.
        return

    with transaction.atomic():
        active_enrollment.status = Enrollment.EnrollmentStatus.PROMOTED
        active_enrollment.end_date = timezone.now().date()
        active_enrollment.save()

        Enrollment.objects.create(
            student=student,
            class_group=target_class,
            start_date=timezone.now().date(),
            status=Enrollment.EnrollmentStatus.ACTIVE,
        )

        # The new class may have a different trainer — follow the
        # student across, same as an Exec-Admin-approved promotion did.
        if target_class.trainer_id and target_class.trainer_id != student.trainer_id:
            student.trainer = target_class.trainer
            student.save(update_fields=['trainer'])
#

# ─── Exam Booking ──────────────────────────────────────────────────────────────
class ExamBooking(models.Model):
    """
    A scheduled sitting of an international certification exam, booked by
    the Test Admin ahead of time. Distinct from InternationalExamAttempt —
    a booking is a calendar appointment; once the exam is actually sat the
    Test Admin records the result as an InternationalExamAttempt (which can
    optionally be linked back here via `attempt`).
    """

    class BookingStatus(models.TextChoices):
        SCHEDULED = 'Scheduled', 'Scheduled'
        COMPLETED = 'Completed', 'Completed'
        CANCELLED = 'Cancelled', 'Cancelled'

    student_module = models.ForeignKey(
        StudentModule,
        on_delete=models.CASCADE,
        related_name='exam_bookings'
    )

    booked_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_bookings_made'
    )

    exam_date = models.DateField()
    exam_time = models.TimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.SCHEDULED
    )

    attempt = models.ForeignKey(
        InternationalExamAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'exam_bookings'
        verbose_name = 'Exam Booking'
        verbose_name_plural = 'Exam Bookings'
        ordering = ['exam_date', 'exam_time']

    def __str__(self):
        return f"{self.student_module} — {self.exam_date} — {self.status}"
