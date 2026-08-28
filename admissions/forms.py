# admissions/forms.py

from django import forms
from .models import Applicant, StudentContact
from academics.models import Campus, Program


# ─── Step 1: Personal Details ─────────────────────────────────────────────────
class PersonalDetailsForm(forms.ModelForm):

    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'id_type', 'id_number', 'gender',
            'nationality', 'residential_status',
            'campus', 'program', 'referral_source',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

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