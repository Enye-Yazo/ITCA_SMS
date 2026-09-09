# admissions/views/__init__.py
"""
`admissions.views` used to be one ~960-line file covering the
application/admissions pipeline, historical onboarding, the student
list/detail/export, and Alumni — split here into one module per concern
so each stays a manageable size:

    applications.py — the multi-step application form + Exec Admin's
                       review pipeline (list/detail/approve/reject/submit)
    onboarding.py    — the historical-onboarding "assign straight to a
                       class" finishing step (application_step itself,
                       shared with a normal application, stays in
                       applications.py)
    students.py      — student list/detail/export and profile actions
                       (set email, add module, delete)
    alumni.py         — the Alumni list

Every name below is re-exported at package level so `admissions/urls.py`
and anything else written as `from . import views` / `views.<name>`
keeps working exactly as before — this was a purely structural split,
not a change to any URL, view name, or behavior.
"""

from .applications import (
    STEPS,
    TOTAL_STEPS,
    application_step,
    application_list,
    application_detail,
    application_approve,
    application_reject,
    application_submit,
)
from .onboarding import onboard_confirm
from .students import (
    _filtered_student_rows,
    student_list,
    student_export,
    student_detail,
    student_set_email,
    student_module_add,
    _delete_student_and_records,
    student_delete,
)
from .alumni import alumni_list

__all__ = [
    'STEPS', 'TOTAL_STEPS',
    'application_step', 'application_list', 'application_detail',
    'application_approve', 'application_reject', 'application_submit',
    'onboard_confirm',
    '_filtered_student_rows', 'student_list', 'student_export',
    'student_detail', 'student_set_email', 'student_module_add',
    '_delete_student_and_records', 'student_delete',
    'alumni_list',
]
