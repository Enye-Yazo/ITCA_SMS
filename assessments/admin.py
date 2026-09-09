# assessments/admin.py

from django.contrib import admin
from .models import (
    StudentModule, LocalAssessment,
    InternationalExamAttempt, AccessKey,
    LearningPlatformCredential, ExamBooking,
    PlatformTable, PlatformColumn, PlatformRow, PlatformRowValue,
)


@admin.register(StudentModule)
class StudentModuleAdmin(admin.ModelAdmin):
    list_display = ['student', 'module', 'status', 'assignment_type']
    list_filter = ['status', 'assignment_type']
    search_fields = ['student__applicant__first_name', 'module__module_code']


@admin.register(LocalAssessment)
class LocalAssessmentAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'competency', 'trainer', 'assessment_date']
    list_filter = ['competency']


@admin.register(InternationalExamAttempt)
class InternationalExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'attempt_number', 'exam_date', 'score', 'pass_threshold', 'exam_result']
    list_filter = ['exam_result']


@admin.register(AccessKey)
class AccessKeyAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'key_type', 'issued_at']
    list_filter = ['key_type']


@admin.register(LearningPlatformCredential)
class LearningPlatformCredentialAdmin(admin.ModelAdmin):
    list_display = ['student', 'platform_name', 'username']
    search_fields = ['student__applicant__first_name', 'platform_name']


@admin.register(ExamBooking)
class ExamBookingAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'exam_date', 'exam_time', 'status', 'booked_by']
    list_filter = ['status']


@admin.register(PlatformTable)
class PlatformTableAdmin(admin.ModelAdmin):
    list_display = ['vendor_name', 'section', 'order']
    list_filter = ['section']


@admin.register(PlatformColumn)
class PlatformColumnAdmin(admin.ModelAdmin):
    list_display = ['table', 'label', 'column_type', 'order']
    list_filter = ['column_type']


@admin.register(PlatformRow)
class PlatformRowAdmin(admin.ModelAdmin):
    list_display = ['table', 'student', 'created_at']


@admin.register(PlatformRowValue)
class PlatformRowValueAdmin(admin.ModelAdmin):
    list_display = ['row', 'column', 'value']
