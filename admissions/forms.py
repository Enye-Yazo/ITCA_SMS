# admissions/forms.py

from django import forms
from .models import Applicant, StudentContact
from academics.models import Campus, Program


# ─── Step 1: Personal Details ─────────────────────────────────────────────────
class PersonalDetailsForm(forms.ModelForm):

    # dd/mm/yyyy via the modern flatpickr widget (base.html auto-inits any
    # .js-datepicker input) rather than the native, browser-locale-dependent
    # <input type="date">. input_formats controls parsing on submit; format
    # controls how an existing value is redisplayed (e.g. re-editing a draft).
    date_of_birth = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(
            format='%d/%m/%Y',
            attrs={'class': 'js-datepicker', 'placeholder': 'dd/mm/yyyy', 'autocomplete': 'off'},
        ),
        error_messages={
            'required': 'Enter the date of birth.',
            'invalid': 'Enter the date as dd/mm/yyyy.',
        },
    )

    # Was already a real field on Applicant (and in this form's
    # Meta.fields) but never actually rendered in step_1_personal.html, so
    # it sat empty on every application — now shown and required. The
    # model field itself stays blank=True/null=True (other, non-form
    # creation paths — historical onboarding backfills, admin — don't need
    # to supply one), so `required=True` is set here at the form level.
    referral_source = forms.ChoiceField(
        choices=Applicant.ReferralSource.choices,
        label='Referral',
        required=True,
        error_messages={'required': 'Select how the applicant heard about ITCA.'},
    )

    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'id_type', 'id_number', 'gender',
            'nationality', 'residential_status',
            'campus', 'program', 'referral_source',
        ]

    def clean_id_number(self):
        """
        Check for duplicate ID numbers across all applications.
        If a match is found, return the existing applicant's reference
        so the view can show the warning banner.
        """
        id_number = self.cleaned_data.get('id_number')

        # Exclude the current instance when editing an existing draft
        existing = Applicant.objects.filter(
            id_number=id_number
        ).exclude(
            pk=self.instance.pk if self.instance.pk else None
        ).first()

        if existing:
            # Attach the existing applicant to the error so the view
            # can display the warning banner with their details
            raise forms.ValidationError(
                f"DUPLICATE:{existing.pk}:{existing.application_reference}"
            )

        return id_number


# ─── Step 2: Contact and Address ──────────────────────────────────────────────
class ContactAddressForm(forms.ModelForm):

    class Meta:
        model = Applicant
        fields = [
            'personal_email', 'phone',
            'residential_address', 'city',
            'province', 'postal_code',
        ]


# ─── Step 3: Education and Disability ────────────────────────────────────────
class EducationDisabilityForm(forms.ModelForm):

    class Meta:
        model = Applicant
        fields = [
            'school_name', 'last_school_year',
            'disability_status', 'popi_consent',
        ]
        widgets = {
            'disability_status': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'popi_consent': (
                'The applicant consents to their data being processed '
                'under POPIA (optional)'
            ),
        }


# ─── Step 4: Next of Kin ─────────────────────────────────────────────────────
class NextOfKinForm(forms.ModelForm):

    class Meta:
        model = StudentContact
        fields = [
            'first_name', 'last_name', 'relationship',
            'cell', 'work_phone', 'email',
        ]
        labels = {
            'cell': 'Cell number',
            'work_phone': 'Work phone (optional)',
            'email': 'Email address (optional)',
        }