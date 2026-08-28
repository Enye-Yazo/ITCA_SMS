# accounts/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import UserRoleForm
from .models import SystemUser


def landing(request):
    """
    Public landing page at '/'. Anonymous visitors see the ITCA landing
    screen with a "Sign in with Microsoft" button. This same view is
    also the post-login redirect target (settings.LOGIN_REDIRECT_URL) —
    once authenticated, a user is routed straight to whichever page is
    the front door for their role rather than ever seeing this screen.
    """
    if request.user.is_authenticated:
        user = request.user
        if user.is_exec_admin:
            return redirect('dashboard:index')
        if user.is_trainer:
            return redirect('assessments:grading_index')
        if user.is_test_admin:
            return redirect('assessments:exam_attempt_list')
        if user.is_data_capturer:
            return redirect('admissions:application_list')
        # Fallback for a role with no dedicated home yet
        return redirect('dashboard:index')

    return render(request, 'accounts/landing.html')


def exec_only(view_func):
    """Restricts a view to Exec Admins only."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_exec_admin:
            messages.error(request, "Only Exec Admins can manage users.")
            return redirect('accounts:landing')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─── User Management ─────────────────────────────────────────────────────────
@login_required
@exec_only
def user_list(request):
    """
    Lets an Exec Admin assign role/campus/active status to any user
    without touching Django admin — each row is its own small form.
    """
    users = SystemUser.objects.select_related('campus').order_by('first_name', 'last_name')

    # Each row gets its own form bound to that user, so the role/campus
    # selects show their current values. The table can't have a <form>
    # wrapping <td> siblings, so each field is tied to an out-of-table
    # <form id="user-form-{pk}"> via the HTML5 form="..." attribute —
    # set here since Django template syntax can't add extra widget attrs.
    user_rows = []
    for user in users:
        row_form = UserRoleForm(instance=user)
        for field in row_form.fields.values():
            field.widget.attrs['form'] = f'user-form-{user.pk}'
        row_form.fields['first_name'].widget.attrs['placeholder'] = 'First name'
        row_form.fields['last_name'].widget.attrs['placeholder'] = 'Last name'
        user_rows.append({'user': user, 'form': row_form})

    context = {'user_rows': user_rows}
    return render(request, 'accounts/user_list.html', context)


@login_required
@exec_only
def user_update(request, pk):
    """
    Updates one user's role/campus/active status. An Exec Admin cannot
    edit their own account here — role/deactivation changes to your own
    account belong in Django admin, where a lockout is harder to trigger
    by accident.
    """
    user = get_object_or_404(SystemUser, pk=pk)

    if request.method != 'POST':
        return redirect('accounts:user_list')

    if user.pk == request.user.pk:
        messages.error(request, "You can't edit your own account here — use Django admin instead.")
        return redirect('accounts:user_list')

    form = UserRoleForm(request.POST, instance=user)
    if form.is_valid():
        form.save()
        messages.success(request, f"{user.full_name} updated.")
    else:
        messages.error(request, f"Could not update {user.full_name} — check the form and try again.")

    return redirect('accounts:user_list')
