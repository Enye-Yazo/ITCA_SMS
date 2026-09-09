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

    path('platform/', views.platform_management, name='platform_management'),
    path('platform/tables/create/', views.platform_table_create, name='platform_table_create'),
    path('platform/tables/<int:table_id>/delete/', views.platform_table_delete, name='platform_table_delete'),
    path('platform/tables/<int:table_id>/columns/create/', views.platform_column_create, name='platform_column_create'),
    path('platform/columns/<int:column_id>/update/', views.platform_column_update, name='platform_column_update'),
    path('platform/columns/<int:column_id>/delete/', views.platform_column_delete, name='platform_column_delete'),
    path('platform/tables/<int:table_id>/rows/create/', views.platform_row_create, name='platform_row_create'),
    path('platform/rows/<int:row_id>/delete/', views.platform_row_delete, name='platform_row_delete'),
    path('platform/cell/update/', views.platform_cell_update, name='platform_cell_update'),
]
