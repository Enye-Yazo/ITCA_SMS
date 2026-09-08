# assessments/forms.py

from django import forms

from academics.models import Module
from admissions.models import Student
from .models import InternationalExamAttempt


class InternationalExamAttemptForm(forms.ModelForm):
    """
    Recorded by the Test Admin. Student and Module are picked
    independently — a StudentModule row doesn't need to already exist;
    the view get_or_creates one as an Elective assignment, since a Test
    Admin may need to record an attempt for a module a student hasn't
    formally been assigned yet.

    student is rendered as a search box (see the template's datalist)
    rather than a giant dropdown, so it stays usable as the student
    list grows. The widget is a HiddenInput because the visible search
    input isn't this field itself — JS resolves the typed name back to
    a student ID and writes it into this hidden field before submit.

    attempt_number is computed server-side (next sequential number for
    the chosen student+module), never entered by hand.
    """
    student = forms.ModelChoiceField(
        queryset=Student.objects.select_related('applicant').order_by(
            'applicant__first_name', 'applicant__last_name'
        ),
        widget=forms.HiddenInput(),
        error_messages={
            'required': 'Search for and select a student.',
            'invalid_choice': 'Select a student from the search results.',
        },
    )

    module = forms.ModelChoiceField(
        # Only modules that actually carry an international exam
        queryset=Module.objects.filter(
            is_international_assessment=True, is_active=True
        ).order_by('module_code'),
        empty_label='Select a module',
        error_messages={'required': 'Select a module.'},
    )

    # Plain ChoiceField rather than a BooleanField Select — avoids the
    # awkward True/False-vs-string coercion and lets us force a real
    # choice (no option is pre-selected by default).
    exam_result = forms.ChoiceField(
        choices=[('', 'Select a result'), ('true', 'Passed'), ('false', 'Failed')],
        error_messages={'required': 'Select whether the student passed or failed.'},
    )

    score = forms.IntegerField(
        min_value=0,
        max_value=1000,
        help_text='Out of 1000 — 700 is the pass mark.',
        error_messages={
            'required': 'Enter the score.',
            'min_value': 'Score can\'t be negative.',
            'max_value': 'Score can\'t exceed 1000.',
        },
    )

    class Meta:
        model = InternationalExamAttempt
        fields = ['exam_date', 'exam_result', 'score']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_exam_result(self):
        return self.cleaned_data['exam_result'] == 'true'
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ExamBookingForm(forms.ModelForm):
    """Test Admin schedules an exam sitting ahead of time."""
    student = forms.ModelChoiceField(
        queryset=Student.objects.select_related('applicant').order_by(
            'applicant__first_name', 'applicant__last_name'
        ),
    )

    module = forms.ModelChoiceField(
        queryset=Module.objects.filter(
            is_international_assessment=True, is_active=True
        ).order_by('module_code'),
    )

    class Meta:
        from .models import ExamBooking
        model = ExamBooking
        fields = ['exam_date', 'exam_time']
