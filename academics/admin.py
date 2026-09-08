# academics/admin.py

from django.contrib import admin
from .models import Campus, Program, Module, ProgramModule, Class, Enrollment, AttendanceRecord


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ['campus_name', 'campus_code', 'is_active']
    search_fields = ['campus_name', 'campus_code']


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ['program_name', 'program_code', 'is_active']
    search_fields = ['program_name', 'program_code']


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = [
        'module_code', 'module_name',
        'is_local_assessment', 'is_international_assessment',
        'certifying_body', 'is_active'
    ]
    search_fields = ['module_code', 'module_name']
    list_filter = ['is_local_assessment', 'is_international_assessment']


@admin.register(ProgramModule)
class ProgramModuleAdmin(admin.ModelAdmin):
    list_display = ['program', 'module', 'is_default']
    list_filter = ['program', 'is_default']


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = [
        'program', 'campus', 'trainer',
        'academic_year', 'cohort', 'is_active'
    ]
    list_filter = ['program', 'campus', 'academic_year', 'cohort']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Mirrors ClassForm's own restriction (academics/forms.py) so a
        # class's trainer can't be set to an Exec Admin (or any non-Trainer
        # role) via Django admin either — an Exec Admin is never a valid
        # fallback trainer, in either entry point.
        if db_field.name == 'trainer':
            from accounts.models import SystemUser, UserRole
            kwargs['queryset'] = SystemUser.objects.filter(role=UserRole.TRAINER)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'class_group', 'start_date', 'status']
    list_filter = ['status', 'class_group__campus', 'class_group__program']

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'class_group', 'date', 'status', 'time_in']
    list_filter = ['status', 'class_group__campus']
    search_fields = ['student__applicant__first_name', 'student__applicant__last_name']
