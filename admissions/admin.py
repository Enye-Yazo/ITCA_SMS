# admissions/admin.py

from django.contrib import admin
from .models import Applicant, StudentContact, Student, Alumni


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'program',
        'campus', 'application_status', 'date_applied'
    ]
    list_filter = ['application_status', 'program', 'campus']
    search_fields = ['first_name', 'last_name', 'id_number', 'reference']
    readonly_fields = ['date_applied']


@admin.register(StudentContact)
class StudentContactAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'relationship', 'cell', 'applicant']
    search_fields = ['first_name', 'last_name', 'applicant__first_name']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'student_email', 'trainer', 'campus', 'program']
    search_fields = [
        'applicant__first_name', 'applicant__last_name',
        'student_email'
    ]
    list_filter = ['applicant__campus', 'applicant__program']


@admin.register(Alumni)
class AlumniAdmin(admin.ModelAdmin):
    list_display = ['student', 'program', 'campus', 'graduation_date']
    list_filter = ['program', 'campus']