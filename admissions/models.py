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
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'
        WAITLISTED = 'Waitlisted', 'Waitlisted'

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
        WORD_OF_MOUTH = 'Word of Mouth', 'Word of Mouth'
        FACEBOOK      = 'Facebook', 'Facebook'
        EXHIBITION    = 'Exhibition', 'Exhibition'
        FIND_A_FRIEND = 'Find a Friend', 'Find a Friend'
        WEBSITE       = 'Website', 'Website'

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

    # ── Application Tracking ──────────────────────────────────────────────────
    date_applied = models.DateField(auto_now_add=True)
    application_status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING
    )
    status_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the status was last changed"
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
        return (
            f"{self.first_name} {self.last_name}"
            f"— {self.application_reference or 'Draft'}"
            )
    
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

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.student_id_code:
            from django.utils import timezone
            year = timezone.now().year
            campus_code = self.applicant.campus.campus_code

            # Count existing students at this campus for this year
            # to determine the next sequence number
            existing_count = Student.objects.filter(
                applicant__campus=self.applicant.campus,
                created_at__year=year
            ).count()

            sequence = str(existing_count).zfill(3)
            self.student_id_code = f"{campus_code}-{year}-{sequence}"
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