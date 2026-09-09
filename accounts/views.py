# accounts/views.py

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .decorators import role_required
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

    return render(request, 'accounts/landing.html', {'debug': settings.DEBUG})


exec_only = role_required('is_exec_admin', "Only Exec Admins can manage users.", 'accounts:landing')


# ─── User Management ─────────────────────────────────────────────────────────
@login_required
@exec_only
def user_list(request):
    """
    Lets an Exec Admin assign role/campus/active status to any user
    without touching Django admin — each row is its own small form.
    """
    # Superuser(s) pinned to the top of the table regardless of name,
    # then everyone else alphabetically.
    users = SystemUser.objects.select_related('campus').order_by(
        '-is_superuser', 'first_name', 'last_name'
    )

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


@login_required
@exec_only
def user_delete(request, pk):
    """
    Removes a user account entirely. Same guards as user_update: an Exec
    Admin can't delete their own account here (use Django admin, where a
    lockout is harder to trigger by accident), and a superuser account
    can't be deleted from this screen at all — only ever via Django
    admin, so the one account that can always fix a broken permissions
    setup can't be removed with a single misclick.
    """
    user = get_object_or_404(SystemUser, pk=pk)

    if request.method != 'POST':
        return redirect('accounts:user_list')

    if user.pk == request.user.pk:
        messages.error(request, "You can't delete your own account here — use Django admin instead.")
        return redirect('accounts:user_list')

    if user.is_superuser:
        messages.error(request, "Superuser accounts can't be deleted here — use Django admin instead.")
        return redirect('accounts:user_list')

    full_name = user.full_name
    user.delete()
    messages.success(request, f"{full_name} has been deleted.")

    return redirect('accounts:user_list')


# ─── Trainer Roster ───────────────────────────────────────────────────────────
@login_required
@exec_only
def trainer_list(request):
    """
    Read-only roster of every Trainer with their assigned campus, active
    student count and formative pass rate — the Exec Admin's overview of
    staffing and performance across both campuses.
    """
    from django.db.models import Prefetch
    from academics.models import Enrollment
    from assessments.models import StudentModule

    trainers = SystemUser.objects.filter(role='trainer').select_related('campus').order_by('first_name')

    rows = []
    total_students = 0
    total_competent = 0
    total_evaluated = 0
    programs_seen = set()

    for trainer in trainers:
        # select_related + the student_modules Prefetch turn this page's
        # query count from ~2-4 extra queries *per student* (each
        # `.is_evaluated`/`.is_competent` check, and each `.program`
        # lookup, used to hit the DB fresh) into 2 queries *per trainer*
        # — this page was making ~120 queries for 4 trainers/~40 students
        # before this fix (see Student.is_evaluated's docstring).
        active_students = list(
            trainer.students.filter(
                enrollments__status=Enrollment.EnrollmentStatus.ACTIVE
            ).distinct().select_related('applicant', 'applicant__program').prefetch_related(
                Prefetch(
                    'student_modules',
                    queryset=StudentModule.objects.select_related('module', 'local_assessment'),
                )
            )
        )
        student_count = len(active_students)
        total_students += student_count

        competent = 0
        evaluated = 0
        program_name = None
        for student in active_students:
            program_name = student.program.program_name if student.program else program_name
            programs_seen.add(program_name)
            if student.is_evaluated:
                evaluated += 1
                if student.is_competent:
                    competent += 1

        pass_rate = round((competent / evaluated) * 100) if evaluated else None
        total_competent += competent
        total_evaluated += evaluated

        rows.append({
            'trainer': trainer,
            'student_count': student_count,
            'pass_rate': pass_rate,
            'program_name': program_name,
        })

    avg_pass_rate = round((total_competent / total_evaluated) * 100) if total_evaluated else 0

    context = {
        'rows': rows,
        'active_trainer_count': trainers.filter(is_active=True).count(),
        'total_students': total_students,
        'avg_pass_rate': avg_pass_rate,
        'program_count': len([p for p in programs_seen if p]),
    }
    return render(request, 'accounts/trainer_list.html', context)


# ─── Invite User ──────────────────────────────────────────────────────────────
@login_required
@exec_only
def user_invite(request):
    """
    Creates a new SystemUser directly (no local password — same as the
    Entra ID auto-provisioning flow, just triggered manually by an Exec
    Admin ahead of that person's first sign-in).
    """
    from .forms import UserInviteForm

    if request.method == 'POST':
        form = UserInviteForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_unusable_password()
            user.save()
            messages.success(request, f"{user.full_name} invited — they can now sign in with Microsoft.")
            return redirect('accounts:user_list')
    else:
        form = UserInviteForm()

    return render(request, 'accounts/user_invite.html', {'form': form})


# ─── Dev-only quick login ─────────────────────────────────────────────────────
def dev_login(request):
    """
    Local-development-only account switcher. Real auth here is Entra ID
    SSO with no local passwords, which makes manually walking a
    multi-role scenario (Data Capturer → Trainer → Test Admin → Exec
    Admin) painful — it would otherwise mean a real Microsoft OAuth
    round-trip per switch, on a separate Microsoft account per role.

    Hard-gated on settings.DEBUG (never True in production per
    itca_sms/settings.py) so this can never become a real auth bypass —
    the check happens first, before anything else, on every request.
    """
    if not settings.DEBUG:
        raise Http404

    users = SystemUser.objects.select_related('campus').order_by('-is_superuser', 'role', 'first_name')
    return render(request, 'accounts/dev_login.html', {'users': users})


@require_POST
def dev_login_as(request, pk):
    """Switches the current session to the chosen user. See dev_login() above."""
    if not settings.DEBUG:
        raise Http404

    user = get_object_or_404(SystemUser, pk=pk)
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f"Dev quick-login: now signed in as {user.full_name} ({user.get_role_display()}).")
    return redirect('accounts:landing')
