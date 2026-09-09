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

    # Minimum score required to pass THIS exam — different certifications
    # (and different versions of the same one over time) have different
    # thresholds, so it's entered per attempt rather than assumed fixed.
    # Pass/Fail is derived from score vs this in the view, never picked
    # by hand — see exam_attempt_record.
    pass_threshold = forms.IntegerField(
        min_value=0,
        max_value=1000,
        help_text='Minimum score (out of 1000) needed to pass this exam.',
        error_messages={
            'required': 'Enter the passing threshold for this exam.',
            'min_value': "Threshold can't be negative.",
            'max_value': "Threshold can't exceed 1000.",
        },
    )

    score = forms.IntegerField(
        min_value=0,
        max_value=1000,
        help_text='Out of 1000.',
        error_messages={
            'required': 'Enter the score.',
            'min_value': 'Score can\'t be negative.',
            'max_value': 'Score can\'t exceed 1000.',
        },
    )

    # dd/mm/yyyy via the modern flatpickr widget rather than the native
    # <input type="date"> picker — see ExamBookingForm.exam_date below for
    # the same treatment.
    exam_date = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(
            format='%d/%m/%Y',
            attrs={'class': 'js-datepicker', 'placeholder': 'dd/mm/yyyy', 'autocomplete': 'off'},
        ),
        error_messages={
            'required': 'Enter the exam date.',
            'invalid': 'Enter the date as dd/mm/yyyy.',
        },
    )

    class Meta:
        model = InternationalExamAttempt
        fields = ['exam_date', 'score']


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

    # dd/mm/yyyy via the modern flatpickr widget rather than the browser-
    # locale-dependent HTML5 date picker. input_formats controls parsing on
    # submit; format controls how an existing value (e.g. after a
    # validation error on another field) is redisplayed.
    exam_date = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(
            format='%d/%m/%Y',
            attrs={'class': 'js-datepicker', 'placeholder': 'dd/mm/yyyy', 'autocomplete': 'off'},
        ),
        error_messages={
            'required': 'Enter the exam date.',
            'invalid': 'Enter the date as dd/mm/yyyy.',
        },
    )

    class Meta:
        from .models import ExamBooking
        model = ExamBooking
        fields = ['exam_date', 'exam_time']
