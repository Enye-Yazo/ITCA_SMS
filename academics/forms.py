# academics/forms.py

from django import forms
from .models import Campus, Program, Module, ProgramModule, Class


class CampusForm(forms.ModelForm):
    class Meta:
        model = Campus
        fields = ['campus_name', 'campus_code', 'is_active']
        labels = {
            'campus_code': 'Short code (e.g. DBN)',
            'is_active': 'Active',
        }


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ['program_name', 'program_code', 'is_active']
        labels = {
            'program_code': 'Short code (e.g. CYB)',
            'is_active': 'Active',
        }


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = [
            'module_name', 'module_code',
            'is_local_assessment', 'is_international_assessment',
            'certifying_body', 'is_active',
        ]
        labels = {
            'is_local_assessment': 'Has local NQF5 assessment',
            'is_international_assessment': 'Has international exam',
            'is_active': 'Active',
        }
        widgets = {
            'certifying_body': forms.TextInput(
                attrs={'placeholder': 'e.g. CompTIA, Microsoft'}
            ),
        }


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = [
            'program', 'campus', 'trainer',
            'academic_year', 'cohort', 'capacity', 'is_active',
        ]
        labels = {
            'is_active': 'Active',
        }
        widgets = {
            'academic_year': forms.NumberInput(
                attrs={'placeholder': 'e.g. 2026'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show trainers in the trainer dropdown
        from accounts.models import SystemUser, UserRole
        self.fields['trainer'].queryset = SystemUser.objects.filter(
            role=UserRole.TRAINER,
            is_active=True
        )


class ProgramModuleForm(forms.ModelForm):
    class Meta:
        model = ProgramModule
        fields = ['program', 'module', 'is_default']
        labels = {
            'is_default': 'Auto-assign to new students in this program',
        }