# accounts/views.py

from django.shortcuts import render, redirect


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
