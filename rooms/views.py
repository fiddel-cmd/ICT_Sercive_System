from django.shortcuts import render

from .models import StudyRoom


def study_room_list(request):
    rooms = StudyRoom.objects.filter(is_active=True)
    return render(request, 'rooms/study_room_list.html', {'rooms': rooms})


def login_page(request):
    return render(request, 'rooms/login.html')


def register_page(request):
    return render(request, 'rooms/register.html')
