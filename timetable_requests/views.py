from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import TimetableRequestForm
from .models import TimetableRequest


def request_home(request):
    return render(request, 'timetable_requests/home.html', {})


@login_required
def request_create(request):
    if request.method == 'POST':
        form = TimetableRequestForm(request.POST)
        if form.is_valid():
            timetable_request = form.save(commit=False)
            timetable_request.requester = request.user
            timetable_request.status = TimetableRequest.STATUS_PENDING_REVIEW
            timetable_request.save()
            messages.success(request, 'Your timetable request has been submitted for review.')
            return redirect('timetable_request_home')
    else:
        form = TimetableRequestForm()

    return render(request, 'timetable_requests/request_form.html', {'form': form})
