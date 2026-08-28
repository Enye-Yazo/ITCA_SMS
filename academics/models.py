# academics/models.py

from django.db import models


# ─── Campus ───────────────────────────────────────────────────────────────────
class Campus(models.Model):
    """
    Represents a physical school campus.
    Seeded with DBN and PMB on first setup.
    Exec Admin can add additional campuses via the portal.
    """
    campus_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Full name of the campus e.g. Durban, Pietermaritzburg"
    )

    campus_code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Short code used in reports e.g. DBN, PMB"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive campuses are hidden from dropdowns but data is retained"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'campuses'
        verbose_name = 'Campus'
        verbose_name_plural = 'Campuses'
        ordering = ['campus_name']

    def __str__(self):
        return f"{self.campus_name} ({self.campus_code})"


# ─── Program ──────────────────────────────────────────────────────────────────
class Program(models.Model):
    """
    A qualification program offered by the school.
    e.g. Cyber Security, Software Development.
    Modules are linked via the ProgramModule junction table.
    """
    program_name = models.CharField(max_length=100, unique=True)

    program_code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Short code displayed on the dashboard e.g. CYB, SFTW"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive programs are hidden from new enrollments but data is retained"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'programs'
        verbose_name = 'Program'
        verbose_name_plural = 'Programs'
        ordering = ['program_name']

    def __str__(self):
        return f"{self.program_name} ({self.program_code})"


# ─── Module ───────────────────────────────────────────────────────────────────
class Module(models.Model):
    """
    A single subject/unit that can belong to one or more programs
    via the ProgramModule junction table.
    e.g. Security+ can appear in both Cyber Security and Software Development.
    """
    module_name = models.CharField(max_length=200)
    module_code = models.CharField(max_length=50, unique=True)

    is_local_assessment = models.BooleanField(
        default=False,
        help_text="Has a local NQF5 assessment graded by the trainer"
    )

    is_international_assessment = models.BooleanField(
        default=False,
        help_text="Has an international certification exam e.g. CompTIA, Microsoft"
    )

    certifying_body = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g. CompTIA, Microsoft — only required if is_international_assessment is True"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'modules'
        verbose_name = 'Module'
        verbose_name_plural = 'Modules'
        ordering = ['module_name']

    def __str__(self):
        return f"{self.module_code} — {self.module_name}"


# ─── Program Module ───────────────────────────────────────────────────────────
class ProgramModule(models.Model):
    """
    Junction table linking programs to modules.
    The is_default flag controls whether new students in this program
    are automatically assigned this module on registration.
    Managed by the Exec Admin via the portal.
    """
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='program_modules'
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='program_modules'
    )

    # If True, this module is auto-assigned when a student registers
    # into this program. Only affects new students.
    is_default = models.BooleanField(
        default=False,
        help_text="Auto-assign this module to new students in this program"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'program_modules'
        verbose_name = 'Program Module'
        verbose_name_plural = 'Program Modules'
        # A module can only be linked to a program once
        unique_together = ['program', 'module']
        ordering = ['program', 'module']

    def __str__(self):
        default_label = " (default)" if self.is_default else ""
        return f"{self.program.program_code} — {self.module.module_code}{default_label}"


# ─── Class (Cohort) ───────────────────────────────────────────────────────────
class Class(models.Model):
    """
    A specific intake of students for a program at a campus in a given year.
    The cohort tracks whether students are New or Returning.
    """

    class CohortChoices(models.TextChoices):
        NEW = 'New', 'New'
        RETURNING = 'Returning', 'Returning'

    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name='classes'
    )

    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        related_name='classes'
    )

    trainer = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes',
        help_text="The trainer responsible for this class"
    )

    academic_year = models.IntegerField(
        help_text="The year this class runs e.g. 2024"
    )

    cohort = models.CharField(
        max_length=20,
        choices=CohortChoices.choices,
        default=CohortChoices.NEW
    )

    capacity = models.IntegerField(
        default=30,
        help_text="Maximum number of students allowed in this class"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'classes'
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'
        ordering = ['-academic_year', 'program', 'campus']
        unique_together = ['program', 'campus', 'academic_year', 'cohort']

    def __str__(self):
        return (
            f"{self.program.program_code} | "
            f"{self.campus.campus_code} | "
            f"{self.academic_year} | "
            f"{self.cohort}"
        )


# ─── Enrollment ───────────────────────────────────────────────────────────────
class Enrollment(models.Model):
    """
    Links a student to a class.
    A student can only have one active enrollment at a time.
    Historical enrollments are retained for reporting.
    """

    class EnrollmentStatus(models.TextChoices):
        ACTIVE = 'Active', 'Active'
        COMPLETED = 'Completed', 'Completed'
        WITHDRAWN = 'Withdrawn', 'Withdrawn'
        PROMOTED = 'Promoted', 'Promoted'

    student = models.ForeignKey(
        'admissions.Student',
        on_delete=models.PROTECT,
        related_name='enrollments'
    )

    class_group = models.ForeignKey(
        Class,
        on_delete=models.PROTECT,
        related_name='enrollments',
        db_column='class_id'
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'enrollments'
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.student} — {self.class_group}"