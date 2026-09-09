# admissions/models.py

from django.db import models
from academics.models import Campus, Program, Class
from django.db.models.signals import post_save
from django.dispatch import receiver

# ─── Applicant ────────────────────────────────────────────────────────────────
class Applicant(models.Model):
    """
    Created by the Data Capturer.
    Approved or rejected by the Exec Admin.
    Unsuccessful applications are retained for one year then purged.
    """

    class ApplicationStatus(models.TextChoices):
        # A Data Capturer's in-progress application — set the moment step 1
        # is first saved, and never shown to an Exec Admin as "Pending"
        # (dashboard/application_list both filter on PENDING specifically).
        # Only application_submit (the real "Submit for approval" action at
        # step 5) moves an application from Draft to Pending.
        DRAFT = 'Draft', 'Draft'
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    class IDType(models.TextChoices):
        SA_ID = 'SA ID', 'South African ID'
        PASSPORT = 'Passport', 'Passport'
        ASYLUM = 'Asylum', 'Asylum Document'

    class Gender(models.TextChoices):
        MALE = 'Male', 'Male'
        FEMALE = 'Female', 'Female'
        OTHER = 'Other', 'Other'
        PREFER_NOT = 'Prefer not to say', 'Prefer not to say'

    class ResidentialStatus(models.TextChoices):
        CITIZEN = 'Citizen', 'Citizen'
        PERMANENT_RESIDENT = 'Permanent Resident', 'Permanent Resident'
        ASYLUM_SEEKER = 'Asylum Seeker', 'Asylum Seeker'
        FOREIGN_NATIONAL = 'Foreign National', 'Foreign National'

    class ReferralSource(models.TextChoices):
        WEBSITE         = 'Website', 'Website'
        WORD_OF_MOUTH   = 'Word Of Mouth', 'Word Of Mouth'
        CAREER_EXPO     = 'Career Expo', 'Career Expo'
        SCHOOL_OUTREACH = 'School Outreach', 'School Outreach'
        SOCIAL_MEDIA    = 'Social Media', 'Social Media'

    # ── Application Tracking ──────────────────────────────────────────────────
    date_applied = models.DateField(auto_now_add=True)

    application_status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING
    )

    status_date = models.DateField(null=True, blank=True)

    # How the applicant heard about ITCA
    referral_source = models.CharField(
        max_length=20,
        choices=ReferralSource.choices,
        blank=True,
        null=True,
        help_text="How did the applicant hear about ITCA?"
    )

    # Auto-generated unique reference e.g. ITCA-2026-00001
    application_reference = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Auto-generated application reference number"
    )

    # ── Campus and Program applied to ─────────────────────────────────────────
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        related_name='applicants'
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name='applicants'
    )

    # ── Personal Details ──────────────────────────────────────────────────────
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    id_number = models.CharField(max_length=50, unique=True)
    id_type = models.CharField(max_length=20, choices=IDType.choices)
    gender = models.CharField(max_length=20, choices=Gender.choices)
    nationality = models.CharField(max_length=100)
    residential_status = models.CharField(
        max_length=30,
        choices=ResidentialStatus.choices
    )

    # ── Contact Details ───────────────────────────────────────────────────────
    personal_email = models.EmailField(
        blank=True,
        null=True
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
        )

    # ── Address ───────────────────────────────────────────────────────────────
    residential_address = models.CharField(
        max_length=255,
         blank=True,
         null=True 
         )
    city = models.CharField(
        max_length=100,
         blank=True,
         null=True 
         )
    province = models.CharField(
        max_length=100,
         blank=True,
         null=True 
        )
    postal_code = models.CharField(
        max_length=10,
         blank=True,
         null=True 
        )

    # ── Education ─────────────────────────────────────────────────────────────
    school_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
        )
    last_school_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Last year the applicant attended school e.g. 2022" 
    )

    # ── Disability ────────────────────────────────────────────────────────────
    disability_status = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Describe any disability or leave blank for none"
    )

    # Set once, at creation, by whichever entry point a Data Capturer used
    # (application_new vs onboard_new) — distinguishes an application that
    # still needs an Exec Admin admission decision from an already-real
    # student whose historical record is just being captured into the
    # system, and whose review step (5) offers "assign to class" instead
    # of "submit for review" as a result.
    is_historical_onboarding = models.BooleanField(
        default=False,
        help_text="True for an existing student being backfilled into the system, rather than a new applicant awaiting an admission decision"
    )

    # POPI Act consent — does not stop application
    popi_consent = models.BooleanField(
        default=False,
        help_text="Records whether the applicant consented to data processing under POPIA. Optional."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'applicant_details'
        verbose_name = 'Applicant'
        verbose_name_plural = 'Applicants'
        ordering = ['-date_applied']

    def __str__(self):
        return (
            f"{self.first_name} {self.last_name} — {self.application_status}"
            f"— {self.application_reference or 'Draft'}"
            )

    @property
    def full_name(self):
        # Deliberately just the name — application_reference is shown as
        # its own column/badge wherever it's needed (applications list,
        # detail view), not appended here. This is also what Student.full_name
        # delegates to, so a bare name here keeps every student-facing
        # table, nav, and message clean of the reference number.
        return f"{self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.application_reference:
            self.application_reference = (
                f"ITCA-{self.date_applied.year}-{self.pk:05d}"
            )
            super().save(update_fields=['application_reference'])


# ─── Emergency Contact ────────────────────────────────────────────────────────
class StudentContact(models.Model):
    """
    Emergency contact linked to an applicant.
    Created by the Data Capturer alongside the applicant profile.
    """
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name='contacts'
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=50)
    cell = models.CharField(max_length=20)
    work_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        db_table = 'student_contact'
        verbose_name = 'Student Contact'
        verbose_name_plural = 'Student Contacts'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.relationship})"


# ─── Student ──────────────────────────────────────────────────────────────────
class Student(models.Model):
    """
    Created automatically when an Applicant is approved by the Exec Admin.
    One-to-one with Applicant — all personal details remain on the Applicant record.
    The student_email is their school-issued email, separate from personal_email.
    """
    applicant = models.OneToOneField(
        Applicant,
        on_delete=models.PROTECT,
        related_name='student_profile'
    )

    # The trainer assigned to this student
    trainer = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )

    # School-issued email for platform access
    student_email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        help_text="School-issued email address for platform access"
    )

    # Auto-generated e.g. DBN-2026-001, resets per campus per year
    student_id_code = models.CharField(
        max_length=30, unique=True, blank=True, null=True,
        help_text="Auto-generated student identifier"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_details'
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        return f"{self.applicant.full_name} ({self.student_id_code})"

    @property
    def full_name(self):
        return self.applicant.full_name

    @property
    def campus(self):
        # Convenience property — campus lives on the applicant record
        return self.applicant.campus

    @property
    def program(self):
        # Convenience property — program lives on the applicant record
        return self.applicant.program

    @property
    def is_evaluated(self):
        """
        True once at least one of the student's assigned NQF5 modules has
        been rated (Competent or Not Yet Competent) — the "has grading
        started" signal used by Reports/dashboard/trainer-roster pass
        rates to decide whether a student counts toward the denominator
        at all.

        Reads through the `student_modules` related manager rather than
        issuing a fresh `LocalAssessment.objects.filter(...)` query —
        this is what lets a queryset of many students avoid an N+1 by
        prefetching once with
        `Prefetch('student_modules', queryset=StudentModule.objects.select_related('module', 'local_assessment'))`
        (see accounts.views.trainer_list and dashboard.views.reports_index,
        the two call sites this used to make ~200 and ~120 queries for a
        few dozen students, before this fix). Calling it on a single
        `Student` fetched without that prefetch still works — it just
        costs one query per module instead of being free.
        """
        from assessments.models import LocalAssessment

        for student_module in self.student_modules.all():
            if not student_module.module.is_local_assessment:
                continue
            assessment = getattr(student_module, 'local_assessment', None)
            if assessment is not None and assessment.competency:
                return True
        return False

    @property
    def is_competent(self):
        """
        True once every NQF5 (local-assessment) module the student is
        assigned is rated Competent. This is deliberately all-or-nothing
        — one module still Not Yet Competent or ungraded means the
        student isn't Competent overall — and requires at least one
        NQF5 module to be assigned, so an untouched student can never
        read as competent. This is also the trigger for automatic
        promotion (assessments.models.auto_promote_on_full_nqf5_pass).

        Same `student_modules`-related-manager approach as `is_evaluated`
        above, for the same N+1 reason — see its docstring.
        """
        from assessments.models import LocalAssessment

        found_local_assessment_module = False
        for student_module in self.student_modules.all():
            if not student_module.module.is_local_assessment:
                continue
            found_local_assessment_module = True
            assessment = getattr(student_module, 'local_assessment', None)
            if assessment is None or assessment.competency != LocalAssessment.Competency.COMPETENT:
                return False

        return found_local_assessment_module

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.student_id_code:
            from django.db import transaction
            from django.utils import timezone
            year = timezone.now().year

            # Locking the Campus row (not just reading Student's count) is
            # what actually prevents a collision here — without it, two
            # Students approved for the same campus at nearly the same
            # moment (two Exec Admins approving in parallel, or a slow/
            # cold-starting request getting double-submitted) can both read
            # the same `existing_count` before either has committed its
            # write, then both try to save the exact same student_id_code.
            # One succeeds; the other hits student_id_code's UNIQUE
            # constraint as an uncaught IntegrityError — a 500 to whoever
            # made that second request — and the whole @transaction.atomic
            # approval (Student + Enrollment + Applicant status) rolls
            # back, so nothing is left half-done, but the approval itself
            # still visibly failed. select_for_update() on the Campus row
            # makes the second save() block until the first one commits,
            # so it recomputes the count fresh and gets the next number
            # instead of colliding — reproduced and confirmed fixed via two
            # threads racing to create a Student for the same campus.
            with transaction.atomic():
                campus = Campus.objects.select_for_update().get(pk=self.applicant.campus_id)

                # Count existing students at this campus for this year
                # to determine the next sequence number
                existing_count = Student.objects.filter(
                    applicant__campus=campus,
                    created_at__year=year
                ).count()

                sequence = str(existing_count).zfill(3)
                self.student_id_code = f"{campus.campus_code}-{year}-{sequence}"
                super().save(update_fields=['student_id_code'])

# ─── Alumni ───────────────────────────────────────────────────────────────────
class Alumni(models.Model):
    """
    Created when a student graduates.
    Student data is retained here permanently for records.
    """
    student = models.OneToOneField(
        Student,
        on_delete=models.PROTECT,
        related_name='alumni_record'
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name='alumni'
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        related_name='alumni'
    )
    graduation_date = models.DateField()

    class Meta:
        db_table = 'alumni'
        verbose_name = 'Alumni'
        verbose_name_plural = 'Alumni'
        ordering = ['-graduation_date']

    def __str__(self):
        return f"{self.student.full_name} — {self.graduation_date.year}"


# ─── Signal: auto-assign default modules ──────────────────────────────────────
@receiver(post_save, sender=Student)
def assign_default_modules(sender, instance, created, **kwargs):
    """
    Fires when a Student is created (i.e. on application approval).
    Snapshots the program's current is_default=True ProgramModule links
    into StudentModule records. Because this only runs at creation time,
    changing a program's defaults afterward never affects students who
    are already registered — only future approvals see the new defaults.
    Creating each StudentModule in turn fires create_local_assessment_slots
    (assessments.models), which builds the 3 empty assessment rows.
    """
    if not created:
        return

    # Imported lazily to avoid a circular import — assessments.models
    # already imports Student from this module at module load time.
    from academics.models import ProgramModule
    from assessments.models import StudentModule

    default_modules = ProgramModule.objects.filter(
        program=instance.applicant.program,
        is_default=True
    )
    for program_module in default_modules:
        StudentModule.objects.get_or_create(
            student=instance,
            module=program_module.module,
            defaults={'assignment_type': StudentModule.AssignmentType.DEFAULT},
        )