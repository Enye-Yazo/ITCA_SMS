# assessments/forms.py

from django import forms
from .models import StudentModule, InternationalExamAttempt, Promotion


class InternationalExamAttemptForm(forms.ModelForm):
    """
    Recorded by the Test Admin.
    attempt_number is computed server-side (next sequential number for
    the chosen student+module), never entered by hand.
    """
    class Meta:
        model = InternationalExamAttempt
        fields = ['student_module', 'exam_date', 'exam_result', 'score']
        labels = {
            'student_module': 'Student — Module',
            'exam_result': 'Result',
            'score': 'Score (optional)',
        }
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
            'exam_result': forms.Select(choices=[(True, 'Passed'), (False, 'Failed')]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only offer modules that actually carry an international exam
        self.fields['student_module'].queryset = (
            StudentModule.objects
            .select_related('student', 'student__applicant', 'module')
            .filter(module__is_international_assessment=True)
            .order_by('student__student_id_code', 'module__module_code')
        )


class PromotionRequestForm(forms.ModelForm):
    """
    Requested by a Trainer for one of their own students' active
    enrollments. target_class is restricted, in the view, to Returning
    classes in the same program and campus as the current enrollment.
    """
    class Meta:
        model = Promotion
        fields = ['target_class', 'notes']
        labels = {
            'target_class': 'Promote to class',
            'notes': 'Notes (optional)',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
