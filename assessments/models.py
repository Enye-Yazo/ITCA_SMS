# assessments/models.py

from django.db import models
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
        null=True,
        blank=True,
        help_text="Numeric score if provided by the certifying body"
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


# ─── Promotion Request ────────────────────────────────────────────────────────
class Promotion(models.Model):
    """
    A request to move a student from one class to another.
    e.g. promoting a New student to Returning in the following year.
    Requested by the Trainer, approved or rejected by the Exec Admin.
    """

    class PromotionStatus(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    # The enrollment being moved from
    current_enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.PROTECT,
        related_name='promotion_requests'
    )

    # The class the student is being moved to
    target_class = models.ForeignKey(
        'academics.Class',
        on_delete=models.PROTECT,
        related_name='incoming_promotions'
    )

    requested_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.PROTECT,
        related_name='promotions_requested'
    )

    reviewed_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promotions_reviewed'
    )

    status = models.CharField(
        max_length=20,
        choices=PromotionStatus.choices,
        default=PromotionStatus.PENDING
    )

    request_date = models.DateField(auto_now_add=True)
    review_date = models.DateField(null=True, blank=True)
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Optional notes from the reviewer"
    )

    class Meta:
        db_table = 'promotions'
        verbose_name = 'Promotion Request'
        verbose_name_plural = 'Promotion Requests'
        ordering = ['-request_date']

    def __str__(self):
        return (
            f"{self.current_enrollment.student.full_name} → "
            f"{self.target_class} — {self.status}"
        )
    # academics/models.py

#