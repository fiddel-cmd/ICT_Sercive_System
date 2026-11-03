from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Programme(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('name',)
        verbose_name = 'programme'
        verbose_name_plural = 'programmes'

    def __str__(self):
        return f'{self.code} - {self.name}'


class StaffProgrammeAssignment(models.Model):
    ROLE_LECTURER = 'lecturer'
    ROLE_TIMETABLE_MANAGER = 'timetable_manager'
    ROLE_PROGRAMME_ADMINISTRATOR = 'programme_administrator'

    ROLE_CHOICES = [
        (ROLE_LECTURER, 'Lecturer'),
        (ROLE_TIMETABLE_MANAGER, 'Timetable Manager'),
        (ROLE_PROGRAMME_ADMINISTRATOR, 'Programme Administrator'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='programme_assignments')
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='staff_assignments')
    role = models.CharField(max_length=40, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_programmes',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'programme', 'role'], name='unique_staff_programme_role'),
        ]
        ordering = ('programme__name', 'user__username')

    def __str__(self):
        return f'{self.user} -> {self.programme} ({self.role})'


class TimetableRequest(models.Model):
    REQUEST_TYPE_ROOM_CHANGE = 'room_change'
    REQUEST_TYPE_MAKEUP_CLASS = 'makeup_class'
    REQUEST_TYPE_TIMETABLE_ADJUSTMENT = 'timetable_adjustment'

    REQUEST_TYPE_CHOICES = [
        (REQUEST_TYPE_ROOM_CHANGE, 'Room Change'),
        (REQUEST_TYPE_MAKEUP_CLASS, 'Makeup Class'),
        (REQUEST_TYPE_TIMETABLE_ADJUSTMENT, 'Timetable Adjustment'),
    ]

    STATUS_PENDING_REVIEW = 'pending_review'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_NEEDS_CLARIFICATION = 'needs_clarification'
    STATUS_APPROVED_PENDING_UPDATE = 'approved_pending_update'
    STATUS_REJECTED = 'rejected'
    STATUS_CONFIRMED_IN_UNITIME = 'confirmed_in_unitime'

    STATUS_CHOICES = [
        (STATUS_PENDING_REVIEW, 'Pending Review'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_NEEDS_CLARIFICATION, 'Needs Clarification'),
        (STATUS_APPROVED_PENDING_UPDATE, 'Approved Pending Update'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CONFIRMED_IN_UNITIME, 'Confirmed in UniTime'),
    ]

    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='timetable_requests')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_timetable_requests')
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default=STATUS_PENDING_REVIEW)

    submitted_at = models.DateTimeField(default=timezone.now)
    title_or_subject = models.CharField(max_length=200)
    course_code = models.CharField(max_length=50, blank=True, default='')
    course_name = models.CharField(max_length=200, blank=True, default='')

    lecture_date = models.DateField()
    lecture_start_time = models.TimeField()
    lecture_end_time = models.TimeField()

    original_room = models.CharField(max_length=200, blank=True, default='')
    preferred_alternative_room = models.CharField(max_length=200, blank=True, default='')

    proposed_date = models.DateField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time = models.TimeField(null=True, blank=True)

    reason = models.TextField()
    review_notes = models.TextField(blank=True, default='')

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_timetable_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    alternative_room_selected = models.CharField(max_length=200, blank=True, default='')
    alternative_room_notes = models.TextField(blank=True, default='')

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_timetable_requests',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    unitime_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_timetable_requests',
    )
    unitime_confirmed_at = models.DateTimeField(null=True, blank=True)
    unitime_confirmation_note = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-submitted_at',)

    def clean(self):
        super().clean()

        if self.request_type == self.REQUEST_TYPE_MAKEUP_CLASS:
            if not self.proposed_date:
                raise ValidationError({'proposed_date': 'A makeup class request must include a proposed date.'})
            if not self.proposed_start_time:
                raise ValidationError({'proposed_start_time': 'A makeup class request must include a proposed start time.'})
            if not self.proposed_end_time:
                raise ValidationError({'proposed_end_time': 'A makeup class request must include a proposed end time.'})

            if self.proposed_end_time <= self.proposed_start_time:
                raise ValidationError({'proposed_end_time': 'Proposed end time must be later than the start time.'})

        if self.status == self.STATUS_APPROVED_PENDING_UPDATE:
            if not self.approved_by or not self.approved_at:
                raise ValidationError('Approved requests must include an approver and approval timestamp.')

        if self.status == self.STATUS_CONFIRMED_IN_UNITIME:
            if not self.approved_by or not self.approved_at:
                raise ValidationError('Confirmed requests must first have an approval record.')
            if not self.unitime_confirmed_by or not self.unitime_confirmed_at:
                raise ValidationError('Confirmed requests must include the UniTime confirmation by-user and timestamp.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.request_type} - {self.title_or_subject} ({self.status})'


class TimetableRequestHistory(models.Model):
    ACTION_SUBMITTED = 'submitted'
    ACTION_REVIEW_STARTED = 'review_started'
    ACTION_CLARIFICATION_REQUESTED = 'clarification_requested'
    ACTION_CLARIFICATION_RECEIVED = 'clarification_received'
    ACTION_APPROVED = 'approved'
    ACTION_REJECTED = 'rejected'
    ACTION_ROOM_SELECTED = 'room_selected'
    ACTION_UNITIME_UPDATE_CONFIRMED = 'unitime_update_confirmed'
    ACTION_CANCELLED = 'cancelled'

    ACTION_CHOICES = [
        (ACTION_SUBMITTED, 'Submitted'),
        (ACTION_REVIEW_STARTED, 'Review Started'),
        (ACTION_CLARIFICATION_REQUESTED, 'Clarification Requested'),
        (ACTION_CLARIFICATION_RECEIVED, 'Clarification Received'),
        (ACTION_APPROVED, 'Approved'),
        (ACTION_REJECTED, 'Rejected'),
        (ACTION_ROOM_SELECTED, 'Room Selected'),
        (ACTION_UNITIME_UPDATE_CONFIRMED, 'UniTime Update Confirmed'),
        (ACTION_CANCELLED, 'Cancelled'),
    ]

    request = models.ForeignKey(TimetableRequest, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    old_status = models.CharField(max_length=40, blank=True, default='')
    new_status = models.CharField(max_length=40, blank=True, default='')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timetable_request_history',
    )
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'{self.request} - {self.action}'
