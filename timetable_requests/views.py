from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import permissions
from .forms import TimetableRequestForm
from .models import TimetableRequest


def request_home(request):
    return render(request, 'timetable_requests/home.html', {})


@login_required
def request_create(request):
    # Users who are not lecturers on any programme cannot submit requests.
    if not permissions.submittable_programmes(request.user).exists():
        return render(request, 'timetable_requests/request_form.html', {'form': None}, status=403)

    if request.method == 'POST':
        form = TimetableRequestForm(request.POST, user=request.user)
        if form.is_valid():
            timetable_request = form.save(commit=False)
            # The requester always comes from the session, never from submitted data.
            timetable_request.requester = request.user
            timetable_request.save()
            messages.success(request, 'Your timetable request has been submitted for review.')
            return redirect('timetable_request_list')
    else:
        form = TimetableRequestForm(user=request.user)

    return render(request, 'timetable_requests/request_form.html', {'form': form})


@login_required
def request_list(request):
    """The logged-in user's own requests, newest first."""
    requests_qs = TimetableRequest.objects.filter(requester=request.user).select_related('programme')
    return render(request, 'timetable_requests/request_list.html', {'timetable_requests': requests_qs})


@login_required
@require_POST
def request_cancel(request, pk):
    # Filtering on requester means other people's requests simply return 404.
    timetable_request = get_object_or_404(TimetableRequest, pk=pk, requester=request.user)
    try:
        timetable_request.cancel(request.user)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    except PermissionDenied as exc:
        messages.error(request, str(exc) or 'You cannot cancel this request.')
    else:
        messages.success(request, 'Your request has been cancelled.')
    return redirect('timetable_request_list')