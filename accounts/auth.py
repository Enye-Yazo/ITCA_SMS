# accounts/auth.py

from django.contrib.auth import get_user_model

from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class ITCAOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Maps Microsoft Entra ID claims onto our custom SystemUser model.

    New users are auto-provisioned on first login as active Data
    Capturers — the lowest-privilege role — since only members of the
    school's own Azure AD tenant can reach this login at all. An Exec
    Admin upgrades their role/campus afterward via Django admin
    (/admin/), which is also where entra_id, role and campus already
    live on SystemUser.

    The library's default create_user() calls
    UserModel.objects.create_user(username, email=email), which does
    not match SystemUserManager's create_user(email, password=None,
    **extra_fields) signature — this override fixes that mismatch.
    """

    def create_user(self, claims):
        UserModel = get_user_model()
        user = UserModel.objects.create_user(
            email=claims.get('email'),
            first_name=claims.get('given_name', ''),
            last_name=claims.get('family_name', ''),
        )
        user.entra_id = claims.get('oid') or claims.get('sub') or ''
        user.save(update_fields=['entra_id'])
        return user

    def update_user(self, user, claims):
        """
        Keeps name and Entra object ID in sync on every subsequent
        login. Never touches role/campus/is_active — those are only
        ever changed by an Exec Admin.
        """
        updated_fields = []

        entra_id = claims.get('oid') or claims.get('sub')
        if entra_id and user.entra_id != entra_id:
            user.entra_id = entra_id
            updated_fields.append('entra_id')

        given_name = claims.get('given_name')
        if given_name and user.first_name != given_name:
            user.first_name = given_name
            updated_fields.append('first_name')

        family_name = claims.get('family_name')
        if family_name and user.last_name != family_name:
            user.last_name = family_name
            updated_fields.append('last_name')

        if updated_fields:
            user.save(update_fields=updated_fields)

        return user
