# academics/urls.py

from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('settings/', views.settings_index, name='settings'),

    path('settings/campuses/add/', views.campus_add, name='campus_add'),
    path('settings/campuses/<int:pk>/edit/', views.campus_edit, name='campus_edit'),
    path('settings/campuses/<int:pk>/delete/', views.campus_delete, name='campus_delete'),

    path('settings/programs/add/', views.program_add, name='program_add'),
    path('settings/programs/<int:pk>/edit/', views.program_edit, name='program_edit'),
    path('settings/programs/<int:pk>/delete/', views.program_delete, name='program_delete'),

    path('settings/modules/add/', views.module_add, name='module_add'),
    path('settings/modules/<int:pk>/edit/', views.module_edit, name='module_edit'),
    path('settings/modules/<int:pk>/delete/', views.module_delete, name='module_delete'),

    path('settings/program-modules/add/', views.program_module_add, name='program_module_add'),
    path('settings/program-modules/<int:pk>/delete/', views.program_module_delete, name='program_module_delete'),

    path('settings/classes/add/', views.class_add, name='class_add'),
    path('settings/classes/<int:pk>/edit/', views.class_edit, name='class_edit'),
    path('settings/classes/<int:pk>/delete/', views.class_delete, name='class_delete'),

    path('settings/calendar/', views.calendar_update, name='calendar_update'),

    path('attendance/', views.attendance_view, name='attendance'),
]