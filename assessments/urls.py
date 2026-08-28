# assessments/urls.py

from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    path('grading/', views.grading_index, name='grading_index'),
    path('grading/<int:student_module_id>/update/', views.grade_update, name='grade_update'),

    path('exams/', views.exam_attempt_list, name='exam_attempt_list'),
    path('exams/record/', views.exam_attempt_record, name='exam_attempt_record'),

    path('promotions/', views.promotion_list, name='promotion_list'),
    path('promotions/request/<int:enrollment_id>/', views.promotion_request, name='promotion_request'),
    path('promotions/<int:promotion_id>/approve/', views.promotion_approve, name='promotion_approve'),
    path('promotions/<int:promotion_id>/reject/', views.promotion_reject, name='promotion_reject'),
]
