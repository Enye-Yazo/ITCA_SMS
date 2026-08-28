# accounts/forms.py

from django import forms
from .models import SystemUser


class UserRoleForm(forms.ModelForm):
    """
    Lets an Exec Admin assign a name, role, campus and active status to
    a SystemUser without needing Django admin.

    first_name/last_name are normally synced from Microsoft Entra ID
    claims on every login (see accounts/auth.py's update_user) — but
    personal Microsoft accounts don't always return given_name/family_name,
    which left some auto-provisioned users with a blank name. They're
    editable here as a manual override for exactly that case. Entra's
    update_user only overwrites a name when the claim is actually
    present, so a manually-set name survives future logins unless Entra
    itself later supplies a different one.

    Deliberately excludes email/entra_id — those are the user's real
    identity from Microsoft and should never be hand-edited.
    """
    class Meta:
        model = SystemUser
        fields = ['first_name', 'last_name', 'role', 'campus', 'is_active']
        labels = {
            'is_active': 'Active — unchecking blocks this user from signing in',
        }
