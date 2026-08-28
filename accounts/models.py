# accounts/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


# ─── User Roles ───────────────────────────────────────────────────────────────
# Defined as constants so they can be imported and used across the project
# e.g. from accounts.models import SystemUser; SystemUser.EXEC_ADMIN
class UserRole(models.TextChoices):
    EXEC_ADMIN = 'exec_admin', 'Executive Admin'
    TEST_ADMIN = 'test_admin', 'Test Admin'
    TRAINER = 'trainer', 'Trainer'
    DATA_CAPTURER = 'data_capturer', 'Data Capturer'


# ─── Custom User Manager ──────────────────────────────────────────────────────
# Tells Django how to create users for our custom model
class SystemUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        # We don't store passwords — Entra ID handles authentication
        # unusable_password means Django will never accept a password login
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.EXEC_ADMIN)
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        # Superuser needs a real password to access Django admin
        # Regular users authenticate via Entra ID and never need this
        user.set_password(password)
        user.save(using=self._db)
        return user


# ─── Custom User Model ────────────────────────────────────────────────────────
class SystemUser(AbstractBaseUser, PermissionsMixin):
    """
    Replaces Django's built-in User model.
    Authentication is handled by Microsoft Entra ID (SSO).
    This model stores the user's role, campus assignment, and Entra identity.
    """

    # Entra ID unique identifier — populated on first login
    entra_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Microsoft Entra ID object ID — set automatically on first login"
    )

    email = models.EmailField(
        unique=True,
        help_text="Must match the user's Microsoft/Outlook email address"
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.DATA_CAPTURER,
        help_text="Controls what this user can see and do in the portal"
    )

    # Campus assignment — null means the user can see all campuses (e.g. Exec Admin)
    campus = models.ForeignKey(
        'academics.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
        help_text="Leave blank for Exec Admins who oversee all campuses"
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required for Django admin access

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = SystemUserManager()

    # Django uses this field as the unique login identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'system_users'
        verbose_name = 'System User'
        verbose_name_plural = 'System Users'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    # ── Role helper properties ─────────────────────────────────────────────────
    # Use these in views and templates instead of comparing strings directly
    # e.g. {% if request.user.is_exec_admin %}
    @property
    def is_exec_admin(self):
        return self.role == UserRole.EXEC_ADMIN

    @property
    def is_trainer(self):
        return self.role == UserRole.TRAINER

    @property
    def is_test_admin(self):
        return self.role == UserRole.TEST_ADMIN

    @property
    def is_data_capturer(self):
        return self.role == UserRole.DATA_CAPTURER