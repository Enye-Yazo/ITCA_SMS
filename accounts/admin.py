
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import SystemUser, UserRole


@admin.register(SystemUser)
class SystemUserAdmin(UserAdmin):
    # Fields shown in the user list
    list_display = [
        'email', 'first_name', 'last_name',
        'role', 'campus', 'is_active'
    ]
    list_filter = ['role', 'campus', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']

    # Override UserAdmin fieldsets to match our custom model
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Role & Campus', {'fields': ('role', 'campus')}),
        ('Entra ID', {'fields': ('entra_id',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name',
                'role', 'campus', 'is_active'
            ),
        }),
    )

    ordering = ['email']