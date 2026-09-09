# academics/models.py

from django.db import models, transaction


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
    are automatically assigned this module on registration — and, since
    linking a new default module (see the signal below), every currently
    active student in that program too, not just future ones.
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
    # into this program — and retroactively to every currently active
    # student in the program too, via the signal below.
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


# ─── Signal: retroactively assign a new default module ────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=ProgramModule)
def backfill_default_module_for_active_students(sender, instance, created, **kwargs):
    """
    When a module is linked to a program as a default, this assigns it
    (as a Default-type StudentModule) to every currently actively-
    enrolled student in that program who doesn't already have it —
    deliberately overriding the "default assignment is a snapshot, only
    affects future students" rule for this one action, per client
    request: an Exec Admin linking a module to a program should
    immediately make it a gradable column for every affected trainer's
    existing students, e.g. Cyber Security's Grading page missing
    MCT06-08 for a student who was admitted before those links existed.
    Only fires on creation — there's no UI to flip is_default on an
    existing link (add/remove only), so an update never needs to re-run
    this.
    """
    if not created or not instance.is_default:
        return

    from assessments.models import StudentModule

    student_ids = Enrollment.objects.filter(
        status=Enrollment.EnrollmentStatus.ACTIVE,
        class_group__program=instance.program,
    ).values_list('student_id', flat=True).distinct()

    already_assigned = StudentModule.objects.filter(
        module=instance.module, student_id__in=student_ids
    ).values_list('student_id', flat=True)

    missing_ids = set(student_ids) - set(already_assigned)

    # .create() rather than bulk_create() — bulk_create skips post_save,
    # which is what creates each new StudentModule's NQF5 rating slot
    # (assessments.models.create_local_assessment_slot). The affected set
    # here is always "students in one program", never large enough for
    # the per-row signal cost to matter.
    for student_id in missing_ids:
        StudentModule.objects.create(
            student_id=student_id, module=instance.module,
            assignment_type=StudentModule.AssignmentType.DEFAULT,
        )


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

# ─── Attendance ───────────────────────────────────────────────────────────────
class AttendanceRecord(models.Model):
    """
    One row per student per calendar day, captured by their trainer on the
    Attendance register. Absent/Late notes are free text (e.g. "arrived
    after 08:30") — mirrors the trainer's daily register in the v6 mockup.
    """

    class Status(models.TextChoices):
        PRESENT = 'Present', 'Present'
        LATE = 'Late', 'Late'
        ABSENT = 'Absent', 'Absent'

    student = models.ForeignKey(
        'admissions.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )

    class_group = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )

    recorded_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_recorded'
    )

    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    time_in = models.TimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_records'
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        unique_together = ['student', 'date']
        ordering = ['-date', 'student']

    def __str__(self):
        return f"{self.student.full_name} — {self.date} — {self.status}"


# ─── Academic Calendar ──────────────────────────────────────────────────────
class AcademicCalendar(models.Model):
    """
    Singleton (always pk=1) holding the current school year's start/end
    dates, set by the Exec Admin — typically 1 Feb to 15 Dec, but
    configurable. `year_end` is the date every actively-enrolled
    New-cohort student is automatically promoted to Returning (see
    `run_end_of_year_promotion` below).

    Promotion here is deliberately purely time-based, not tied to any
    assessment result — NQF5 modules only start being assessed once a
    student reaches their Returning year, so NQF5 completion can no
    longer gate the New -> Returning move the way the original
    "Automatic Promotion" design did. That competency-based check still
    exists, just retargeted: a Returning student who passes every NQF5
    module now graduates straight to Alumni instead (see
    assessments.models.auto_graduate_on_full_nqf5_pass).
    """
    year_start = models.DateField(help_text="e.g. 1 February — informational; nothing is automated off this date yet.")
    year_end = models.DateField(help_text="e.g. 15 December — New-cohort students are automatically promoted to Returning on this date.")

    # Which year_end.year the automatic promotion has already run for —
    # prevents re-running it every time run_end_of_year_promotion() is
    # checked (it's checked on every Exec Admin dashboard load) once
    # it's already fired for the current cycle.
    last_promoted_year = models.IntegerField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'academic_calendar'
        verbose_name = 'Academic Calendar'
        verbose_name_plural = 'Academic Calendar'

    def __str__(self):
        return f"{self.year_start:%d %b} – {self.year_end:%d %b}"

    @classmethod
    def load(cls):
        """Singleton accessor — created with sensible defaults on first use."""
        from django.utils import timezone
        today = timezone.now().date()
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'year_start': today.replace(month=2, day=1),
            'year_end': today.replace(month=12, day=15),
        })
        return obj


def run_end_of_year_promotion():
    """
    Promotes every actively-enrolled New-cohort student to the matching
    Returning class (same program/campus), the moment today reaches the
    configured `AcademicCalendar.year_end` — exactly once per cycle,
    guarded by `last_promoted_year`.

    There's no scheduled-task infrastructure in this app (no Celery, no
    cron) — this is called lazily from the top of the Exec Admin
    dashboard on every load, cheap and idempotent since it no-ops
    instantly once already run for the year. `promote_new_cohort_students`
    (a management command) calls this too, for a real cron / Azure
    Container Apps Job to trigger instead, if one gets set up later —
    the lazy dashboard check is a stopgap, not the intended long-term
    mechanism.

    Matches the target Returning class by program+campus+active only,
    not academic_year — the two cohorts' academic_year labels don't
    consistently line up in the existing data (e.g. a "New 2026" class's
    Returning counterpart is sometimes labelled 2025, from before this
    convention existed), and in practice there's only one active
    Returning class per program/campus at a time regardless of its label.
    """
    from django.utils import timezone

    calendar = AcademicCalendar.load()
    today = timezone.now().date()

    if today < calendar.year_end:
        return 0
    if calendar.last_promoted_year == calendar.year_end.year:
        return 0  # already run for this cycle

    promoted = 0
    skipped = 0
    active_new_enrollments = Enrollment.objects.filter(
        status=Enrollment.EnrollmentStatus.ACTIVE,
        class_group__cohort=Class.CohortChoices.NEW,
    ).select_related('student', 'class_group__program', 'class_group__campus')

    for enrollment in active_new_enrollments:
        target_class = Class.objects.filter(
            program=enrollment.class_group.program,
            campus=enrollment.class_group.campus,
            cohort=Class.CohortChoices.RETURNING,
            is_active=True,
        ).first()

        if not target_class:
            # No Returning class for this program/campus yet — leave the
            # student where they are, and don't mark this cycle as done
            # below, so this re-checks (and succeeds) on the next lazy
            # trigger once an Exec Admin creates one.
            skipped += 1
            continue

        with transaction.atomic():
            enrollment.status = Enrollment.EnrollmentStatus.PROMOTED
            enrollment.end_date = today
            enrollment.save()

            Enrollment.objects.create(
                student=enrollment.student,
                class_group=target_class,
                start_date=today,
                status=Enrollment.EnrollmentStatus.ACTIVE,
            )

            if target_class.trainer_id and target_class.trainer_id != enrollment.student.trainer_id:
                enrollment.student.trainer = target_class.trainer
                enrollment.student.save(update_fields=['trainer'])

        promoted += 1

    # Only mark the cycle done once every eligible student actually found
    # a Returning class — otherwise the guard would permanently strand
    # the skipped ones until the Exec Admin happens to change year_end.
    if skipped == 0:
        calendar.last_promoted_year = calendar.year_end.year
        calendar.save(update_fields=['last_promoted_year'])

    return promoted
