# academics/management/commands/promote_new_cohort_students.py

from django.core.management.base import BaseCommand

from academics.models import run_end_of_year_promotion


class Command(BaseCommand):
    """
    Promotes every actively-enrolled New-cohort student to their
    matching Returning class, if today has reached the Exec Admin's
    configured AcademicCalendar.year_end (no-ops otherwise, and no-ops
    again if already run for this cycle).

    This is also triggered lazily on every Exec Admin dashboard load
    (dashboard/views.py), since there's no cron/Celery in this app yet —
    this command exists so a real scheduled trigger (e.g. an Azure
    Container Apps Job, or a host cron job calling `manage.py` inside
    the container) can be wired up later instead of relying on that.
    """
    help = "Promotes New-cohort students to Returning once the configured academic year end date has passed."

    def handle(self, *args, **options):
        promoted = run_end_of_year_promotion()
        if promoted:
            self.stdout.write(self.style.SUCCESS(f"Promoted {promoted} student(s) from New to Returning."))
        else:
            self.stdout.write("No students promoted (year end not yet reached, already run for this cycle, or nobody eligible).")
