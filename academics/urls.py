# academics/urls.py

from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('settings/', views.settings_index, name='settings'),

    path('settings/campuses/add/', views.campus_add, name='campus_add'),
    path('settings/campuses/<int:pk>/edit/', views.campus_edit, name='campus_edit'),

    path('settings/programs/add/', views.program_add, name='program_add'),
    path('settings/programs/<int:pk>/edit/', views.program_edit, name='program_edit'),

    path('settings/modules/add/', views.module_add, name='module_add'),
    path('settings/modules/<int:pk>/edit/', views.module_edit, name='module_edit'),

    path('settings/program-modules/add/', views.program_module_add, name='program_module_add'),
    path('settings/program-modules/<int:pk>/delete/', views.program_module_delete, name='program_module_delete'),

    path('settings/classes/add/', views.class_add, name='class_add'),
    path('settings/classes/<int:pk>/edit/', views.class_edit, name='class_edit'),
]