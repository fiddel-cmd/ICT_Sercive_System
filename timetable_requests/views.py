from django.shortcuts import render


def request_home(request):
    return render(request, 'timetable_requests/home.html', {})
