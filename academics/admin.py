# academics/admin.py

from django.contrib import admin
from .models import Campus, Program, Module, ProgramModule, Class, Enrollment


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


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'class_group', 'start_date', 'status']
    list_filter = ['status', 'class_group__campus', 'class_group__program']