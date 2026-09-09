# accounts/decorators.py
"""
Shared role-check view decorators.

Before this refactor, the same "redirect + flash an error message if the
logged-in user doesn't have this role" pattern was copy-pasted as a private
function in three different files: `accounts.views.exec_only`,
`academics.views.exec_only`, `academics.views.trainer_only`, and
`assessments.views.trainer_only`/`test_admin_only` — five near-identical
function bodies differing only in which role attribute they checked, what
message they flashed, and where they redirected to.

`role_required` factors the actual logic (the part that matters — checking
the attribute, flashing the message, redirecting, otherwise calling the
view) into one place. Each app still gets its own bare `@exec_only` /
`@trainer_only` / `@test_admin_only` name to decorate views with — it's
just built once here, at import time, with that app's own message and
redirect target, instead of redefining the whole wrapper:

    exec_only = role_required('is_exec_admin', "Only Exec Admins can access Settings.", 'dashboard:index')

This preserves every existing call site's exact message text and redirect
target — a purely structural de-duplication, not a behavior change.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def role_required(role_attr, message, redirect_to='dashboard:index'):
    """
    Returns a decorator that restricts a view to users for whom
    `getattr(request.user, role_attr)` is truthy (e.g. 'is_exec_admin',
    'is_trainer', 'is_test_admin', 'is_data_capturer'). Any other user is
    flashed `message` as an error and redirected to `redirect_to`.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not getattr(request.user, role_attr):
                messages.error(request, message)
                return redirect(redirect_to)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
