# assessments/urls.py

from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    path('grading/', views.grading_index, name='grading_index'),
    path('grading/<int:student_module_id>/update/', views.grade_update, name='grade_update'),

    path('grading/int-cert/', views.trainer_intcert_view, name='trainer_intcert'),

    path('exams/', views.exam_attempt_list, name='exam_attempt_list'),
    path('exams/record/', views.exam_attempt_record, name='exam_attempt_record'),

    path('bookings/', views.booking_list, name='booking_list'),
]
