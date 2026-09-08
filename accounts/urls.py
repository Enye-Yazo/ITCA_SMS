# accounts/urls.py

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.landing, name='landing'),

    path('users/', views.user_list, name='user_list'),
    path('users/invite/', views.user_invite, name='user_invite'),
    path('users/<int:pk>/update/', views.user_update, name='user_update'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    path('trainers/', views.trainer_list, name='trainer_list'),

    # DEBUG-only account switcher — see accounts.views.dev_login for the guard.
    path('dev-login/', views.dev_login, name='dev_login'),
    path('dev-login/<int:pk>/', views.dev_login_as, name='dev_login_as'),
]
