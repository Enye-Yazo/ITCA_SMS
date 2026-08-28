# accounts/urls.py

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.landing, name='landing'),

    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/update/', views.user_update, name='user_update'),
]
