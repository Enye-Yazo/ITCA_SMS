# admissions/urls.py

from django.urls import path
from . import views

app_name = 'admissions'

urlpatterns = [
    # Data Capturer — application form steps
    path(
        'applications/new/',
        views.application_step,
        {'step': 1},
        name='application_new'
    ),
    # Onboard an existing student's historical data — same 4-step form,
    # but step 5 assigns straight into a class instead of submitting for
    # an Exec Admin admission decision. See application_step's
    # `historical` kwarg.
    path(
        'applications/onboard/',
        views.application_step,
        {'step': 1, 'historical': True},
        name='onboard_new'
    ),
    path(
        'applications/<int:applicant_id>/onboard/',
        views.onboard_confirm,
        name='onboard_confirm'
    ),
    path(
        'applications/<int:applicant_id>/step/<int:step>/',
        views.application_step,
        name='application_step'
    ),

    # Exec Admin — applications list and detail
    path(
        'applications/',
        views.application_list,
        name='application_list'
    ),
    path(
        'applications/<int:applicant_id>/',
        views.application_detail,
        name='application_detail'
    ),

    # Exec Admin — approve or reject
    path(
        'applications/<int:applicant_id>/approve/',
        views.application_approve,
        name='application_approve'
    ),
    path(
        'applications/<int:applicant_id>/reject/',
        views.application_reject,
        name='application_reject'
    ),
        path(
        'applications/<int:applicant_id>/submit/',
        views.application_submit,
        name='application_submit'
    ),

    # Exec Admin / Trainer — student list and detail
    path(
        'students/',
        views.student_list,
        name='student_list'
    ),
    path(
        'students/export/',
        views.student_export,
        name='student_export'
    ),
    path(
        'students/<int:student_id>/',
        views.student_detail,
        name='student_detail'
    ),
    path(
        'students/<int:student_id>/email/',
        views.student_set_email,
        name='student_set_email'
    ),
    path(
        'students/<int:student_id>/modules/add/',
        views.student_module_add,
        name='student_module_add'
    ),
    path(
        'students/<int:student_id>/delete/',
        views.student_delete,
        name='student_delete'
    ),

    # Exec Admin — Alumni
    path(
        'alumni/',
        views.alumni_list,
        name='alumni_list'
    ),
]