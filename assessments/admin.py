# assessments/admin.py

from django.contrib import admin
from .models import (
    StudentModule, LocalAssessment,
    InternationalExamAttempt, AccessKey,
    LearningPlatformCredential, Promotion
)


@admin.register(StudentModule)
class StudentModuleAdmin(admin.ModelAdmin):
    list_display = ['student', 'module', 'status', 'assignment_type']
    list_filter = ['status', 'assignment_type']
    search_fields = ['student__applicant__first_name', 'module__module_code']


@admin.register(LocalAssessment)
class LocalAssessmentAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'trainer', 'mark', 'competent', 'assessment_date']
    list_filter = ['competent']


@admin.register(InternationalExamAttempt)
class InternationalExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'attempt_number', 'exam_date', 'exam_result', 'score']
    list_filter = ['exam_result']


@admin.register(AccessKey)
class AccessKeyAdmin(admin.ModelAdmin):
    list_display = ['student_module', 'key_type', 'issued_at']
    list_filter = ['key_type']


@admin.register(LearningPlatformCredential)
class LearningPlatformCredentialAdmin(admin.ModelAdmin):
    list_display = ['student', 'platform_name', 'username']
    search_fields = ['student__applicant__first_name', 'platform_name']


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = [
        'current_enrollment', 'target_class',
        'requested_by', 'status', 'request_date'
    ]
    list_filter = ['status']