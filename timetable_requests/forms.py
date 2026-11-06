from django import forms

from . import permissions
from .models import Room, TimetableRequest


class TimetableRequestForm(forms.ModelForm):
    """Submission form. Pass `user=request.user` so the programme list is restricted."""

    class Meta:
        model = TimetableRequest
        fields = [
            'programme',
            'request_type',
            'title_or_subject',
            'course_code',
            'course_name',
            'lecture_date',
            'lecture_start_time',
            'lecture_end_time',
            'original_room',
            'preferred_alternative_room',
            'proposed_date',
            'proposed_start_time',
            'proposed_end_time',
            'reason',
        ]
        widgets = {
            'lecture_date': forms.DateInput(attrs={'type': 'date'}),
            'lecture_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'lecture_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'proposed_date': forms.DateInput(attrs={'type': 'date'}),
            'proposed_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'proposed_end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Only programmes where the user is an active lecturer are valid choices,
        # so a forged POST for any other programme fails validation.
        self.fields['programme'].queryset = permissions.submittable_programmes(user)
        self.fields['original_room'].queryset = Room.objects.filter(is_active=True)
        self.fields['preferred_alternative_room'].queryset = Room.objects.filter(is_active=True)
        