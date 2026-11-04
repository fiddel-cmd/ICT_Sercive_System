from django import forms

from .models import Programme, Room, TimetableRequest


class TimetableRequestForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['programme'].queryset = Programme.objects.filter(is_active=True)
        self.fields['original_room'].queryset = Room.objects.filter(is_active=True)
        self.fields['preferred_alternative_room'].queryset = Room.objects.filter(is_active=True)
