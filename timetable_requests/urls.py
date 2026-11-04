from django.urls import path

from . import views

urlpatterns = [
    path('', views.request_home, name='timetable_request_home'),
    path('new/', views.request_create, name='timetable_request_create'),
]
