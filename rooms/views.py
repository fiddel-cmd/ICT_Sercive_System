from django.shortcuts import render

from .models import StudyRoom

# List all the available rooms 
def study_room_list(request):
    rooms = StudyRoom.objects.filter(is_active=True)
    return render(request, 'rooms/study_room_list.html', {'rooms': rooms})

# vLogin page view
def login_page(request):
    return render(request, 'rooms/login.html')

# Registration page view
def register_page(request):
    return render(request, 'rooms/register.html')