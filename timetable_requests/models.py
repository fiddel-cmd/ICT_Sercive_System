from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models, transaction
from django.utils import timezone


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class TimeStampedModel(models.Model):
    """Abstract base: created_at is set once, updated_at refreshes on every save."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

class Programme(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'programme'
        verbose_name_plural = 'programmes'

    def __str__(self):
        return f'{self.code} - {self.name}'


class Room(TimeStampedModel):
    """A bookable room. Replaces free-text room fields so typos can't creep in."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200, blank=True, default='')
    building = models.CharField(max_length=200, blank=True, default='')
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('building', 'code')

    def __str__(self):
        return f'{self.code} - {self.name}' if self.name else self.code


class StaffProgrammeAssignment(TimeStampedModel):
    ROLE_LECTURER = 'lecturer'
    ROLE_TIMETABLE_MANAGER = 'timetable_manager'
    ROLE_PROGRAMME_ADMINISTRATOR = 'programme_administrator'

    ROLE_CHOICES = [
        (ROLE_LECTURER, 'Lecturer'),
        (ROLE_TIMETABLE_MANAGER, 'Timetable Manager'),
        (ROLE_PROGRAMME_ADMINISTRATOR, 'Programme Administrator'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='programme_assignments'
    )
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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'programme', 'role'], name='unique_staff_programme_role'),
        ]
        ordering = ('programme__name', 'user__username')

    def __str__(self):
        return f'{self.user} -> {self.programme} ({self.get_role_display()})'


# ---------------------------------------------------------------------------
# Timetable requests
# ---------------------------------------------------------------------------

class TimetableRequest(TimeStampedModel):
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
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING_REVIEW, 'Pending Review'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_NEEDS_CLARIFICATION, 'Needs Clarification'),
        (STATUS_APPROVED_PENDING_UPDATE, 'Approved Pending Update'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CONFIRMED_IN_UNITIME, 'Confirmed in UniTime'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # The state machine: which status may follow which. Anything not listed is illegal.
    # Terminal states (rejected, confirmed, cancelled) have no way out.
    ALLOWED_TRANSITIONS = {
        STATUS_PENDING_REVIEW: {STATUS_UNDER_REVIEW, STATUS_REJECTED, STATUS_CANCELLED},
        STATUS_UNDER_REVIEW: {
            STATUS_NEEDS_CLARIFICATION,
            STATUS_APPROVED_PENDING_UPDATE,
            STATUS_REJECTED,
            STATUS_CANCELLED,
        },
        STATUS_NEEDS_CLARIFICATION: {STATUS_UNDER_REVIEW, STATUS_REJECTED, STATUS_CANCELLED},
        STATUS_APPROVED_PENDING_UPDATE: {STATUS_CONFIRMED_IN_UNITIME},
        STATUS_REJECTED: set(),
        STATUS_CONFIRMED_IN_UNITIME: set(),
        STATUS_CANCELLED: set(),
    }

    # Statuses in which a reviewer may still pick or change the alternative room.
    ROOM_SELECTABLE_STATUSES = {STATUS_UNDER_REVIEW, STATUS_APPROVED_PENDING_UPDATE}

    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='timetable_requests')
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_timetable_requests'
    )
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default=STATUS_PENDING_REVIEW)

    submitted_at = models.DateTimeField(default=timezone.now)
    title_or_subject = models.CharField(max_length=200)
    course_code = models.CharField(max_length=50, blank=True, default='')
    course_name = models.CharField(max_length=200, blank=True, default='')

    lecture_date = models.DateField()
    lecture_start_time = models.TimeField()
    lecture_end_time = models.TimeField()

    original_room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='original_room_requests'
    )
    preferred_alternative_room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='preferred_room_requests'
    )

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

    alternative_room_selected = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='selected_room_requests'
    )
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

    class Meta:
        ordering = ('-submitted_at',)
        indexes = [
            models.Index(fields=['programme', 'status'], name='req_programme_status_idx'),
            models.Index(fields=['requester', '-submitted_at'], name='req_requester_submitted_idx'),
        ]
        constraints = [
            # Database-level safety net, in addition to clean().
            # (On Django < 5.1 use `check=` instead of `condition=`.)
            models.CheckConstraint(
                condition=models.Q(lecture_end_time__gt=models.F('lecture_start_time')),
                name='request_lecture_end_after_start',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(proposed_start_time__isnull=True)
                    | models.Q(proposed_end_time__isnull=True)
                    | models.Q(proposed_end_time__gt=models.F('proposed_start_time'))
                ),
                name='request_proposed_end_after_start',
            ),
        ]

    # -- status tracking ----------------------------------------------------
    # Remember the status as loaded from the DB so clean() can tell whether
    # the status is being changed, and whether that change is legal.

    _original_status = None

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_status = instance.__dict__.get('status')
        return instance

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._original_status = self.__dict__.get('status')

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    # -- validation ---------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        def add(field, message):
            errors.setdefault(field, []).append(message)

        status_labels = dict(self.STATUS_CHOICES)

        # 1. Lecture times
        if self.lecture_start_time and self.lecture_end_time:
            if self.lecture_end_time <= self.lecture_start_time:
                add('lecture_end_time', 'Lecture end time must be later than the start time.')

        # 2. Proposed slot: required for makeup classes, and all-or-nothing otherwise.
        proposed = {
            'proposed_date': self.proposed_date,
            'proposed_start_time': self.proposed_start_time,
            'proposed_end_time': self.proposed_end_time,
        }
        any_proposed = any(value is not None for value in proposed.values())
        if self.request_type == self.REQUEST_TYPE_MAKEUP_CLASS or any_proposed:
            for field, value in proposed.items():
                if value is None:
                    add(field, 'This is required when proposing a new slot (always required for makeup classes).')
            if self.proposed_start_time and self.proposed_end_time:
                if self.proposed_end_time <= self.proposed_start_time:
                    add('proposed_end_time', 'Proposed end time must be later than the start time.')

        # 3. Status-specific records
        if self.status in (self.STATUS_APPROVED_PENDING_UPDATE, self.STATUS_CONFIRMED_IN_UNITIME):
            if not (self.approved_by_id and self.approved_at):
                add(NON_FIELD_ERRORS, 'Approved requests must include an approver and approval timestamp.')

        if self.status == self.STATUS_CONFIRMED_IN_UNITIME:
            if not (self.unitime_confirmed_by_id and self.unitime_confirmed_at):
                add(
                    NON_FIELD_ERRORS,
                    'Confirmed requests must include the UniTime confirmation user and timestamp.',
                )

        if self.status == self.STATUS_REJECTED and not self.review_notes.strip():
            add('review_notes', 'Please record the reason for rejecting this request.')

        # 4. Status transitions
        original = self._original_status
        if not self._state.adding and original and original != self.status:
            if self.status not in self.ALLOWED_TRANSITIONS.get(original, set()):
                add(
                    'status',
                    f'A request cannot move from "{status_labels.get(original, original)}" '
                    f'to "{status_labels.get(self.status, self.status)}".',
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self.full_clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                # Every request starts its audit trail automatically.
                TimetableRequestHistory.objects.create(
                    request=self,
                    action=TimetableRequestHistory.ACTION_SUBMITTED,
                    new_status=self.status,
                    performed_by=self.requester,
                )
        self._original_status = self.status

    # -- workflow methods ---------------------------------------------------
    # Use these instead of editing `status` by hand: each one validates the
    # transition, fills the right audit fields, saves, and writes the history
    # row, all inside a single transaction.

    def _log(self, action, old_status, new_status, user, note=''):
        return TimetableRequestHistory.objects.create(
            request=self,
            action=action,
            old_status=old_status,
            new_status=new_status,
            performed_by=user,
            note=note,
        )

    @transaction.atomic
    def _transition(self, new_status, action, user, note='', **fields):
        old_status = self.status
        if not self.can_transition_to(new_status):
            labels = dict(self.STATUS_CHOICES)
            raise ValidationError(
                f'A request cannot move from "{labels[old_status]}" to "{labels[new_status]}".'
            )

        previous = {name: getattr(self, name) for name in fields}
        self.status = new_status
        for name, value in fields.items():
            setattr(self, name, value)

        try:
            self.save()
        except ValidationError:
            # Leave the in-memory object as it was if the change was rejected.
            self.status = old_status
            for name, value in previous.items():
                setattr(self, name, value)
            raise

        self._log(action, old_status, new_status, user, note)
        return self

    def start_review(self, user, note=''):
        return self._transition(
            self.STATUS_UNDER_REVIEW,
            TimetableRequestHistory.ACTION_REVIEW_STARTED,
            user,
            note,
            reviewed_by=user,
            reviewed_at=timezone.now(),
        )

    def request_clarification(self, user, note):
        if not note or not note.strip():
            raise ValidationError('Explain what clarification is needed.')
        return self._transition(
            self.STATUS_NEEDS_CLARIFICATION,
            TimetableRequestHistory.ACTION_CLARIFICATION_REQUESTED,
            user,
            note,
            review_notes=note,
        )

    def receive_clarification(self, user, note=''):
        return self._transition(
            self.STATUS_UNDER_REVIEW,
            TimetableRequestHistory.ACTION_CLARIFICATION_RECEIVED,
            user,
            note,
        )

    def approve(self, user, note=''):
        return self._transition(
            self.STATUS_APPROVED_PENDING_UPDATE,
            TimetableRequestHistory.ACTION_APPROVED,
            user,
            note,
            approved_by=user,
            approved_at=timezone.now(),
        )

    def reject(self, user, note):
        return self._transition(
            self.STATUS_REJECTED,
            TimetableRequestHistory.ACTION_REJECTED,
            user,
            note,
            review_notes=note or '',
            reviewed_by=user,
            reviewed_at=timezone.now(),
        )

    def confirm_in_unitime(self, user, note=''):
        return self._transition(
            self.STATUS_CONFIRMED_IN_UNITIME,
            TimetableRequestHistory.ACTION_UNITIME_UPDATE_CONFIRMED,
            user,
            note,
            unitime_confirmed_by=user,
            unitime_confirmed_at=timezone.now(),
            unitime_confirmation_note=note,
        )

    def cancel(self, user, note=''):
        if user.pk != self.requester_id:
            raise ValidationError('Only the requester can cancel a request.')
        return self._transition(
            self.STATUS_CANCELLED,
            TimetableRequestHistory.ACTION_CANCELLED,
            user,
            note,
        )

    @transaction.atomic
    def select_alternative_room(self, room, user, notes=''):
        """Record the chosen alternative room. This is not a status change."""
        if self.status not in self.ROOM_SELECTABLE_STATUSES:
            raise ValidationError('A room can only be selected while the request is under review or approved.')
        self.alternative_room_selected = room
        self.alternative_room_notes = notes
        self.save()
        self._log(TimetableRequestHistory.ACTION_ROOM_SELECTED, self.status, self.status, user, notes)
        return self

    def __str__(self):
        return f'{self.get_request_type_display()} - {self.title_or_subject} ({self.get_status_display()})'


class TimetableRequestHistory(models.Model):
    """Append-only audit log. Rows are created by TimetableRequest, never edited."""

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        verbose_name_plural = 'timetable request history'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('History entries are append-only and cannot be edited.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.request} - {self.get_action_display()}'