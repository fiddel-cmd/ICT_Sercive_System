from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Programme,
    Room,
    StaffProgrammeAssignment,
    TimetableRequest,
    TimetableRequestHistory,
)


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'building', 'capacity', 'is_active')
    list_filter = ('is_active', 'building')
    search_fields = ('code', 'name', 'building')


@admin.register(StaffProgrammeAssignment)
class StaffProgrammeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'programme', 'role', 'is_active', 'assigned_by', 'assigned_at')
    list_filter = ('role', 'is_active', 'programme')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'programme__name')
    autocomplete_fields = ('user', 'programme', 'assigned_by')
    list_select_related = ('user', 'programme', 'assigned_by')


class TimetableRequestHistoryInline(admin.TabularInline):
    """Read-only timeline shown at the bottom of each request."""

    model = TimetableRequestHistory
    extra = 0
    can_delete = False
    fields = ('created_at', 'action', 'old_status', 'new_status', 'performed_by', 'note')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TimetableRequest)
class TimetableRequestAdmin(admin.ModelAdmin):
    list_display = (
        'title_or_subject',
        'request_type',
        'programme',
        'requester',
        'status',
        'lecture_date',
        'submitted_at',
    )
    list_filter = ('status', 'request_type', 'programme', 'lecture_date')
    search_fields = (
        'title_or_subject',
        'course_code',
        'course_name',
        'requester__username',
        'requester__first_name',
        'requester__last_name',
    )
    date_hierarchy = 'submitted_at'
    list_select_related = ('programme', 'requester')
    autocomplete_fields = (
        'programme',
        'requester',
        'original_room',
        'preferred_alternative_room',
        'alternative_room_selected',
    )
    inlines = [TimetableRequestHistoryInline]

    fieldsets = (
        ('Request', {
            'fields': ('programme', 'requester', 'request_type', 'status', 'title_or_subject', 'reason'),
        }),
        ('Lecture', {
            'fields': (
                'course_code', 'course_name',
                'lecture_date', 'lecture_start_time', 'lecture_end_time',
                'original_room', 'preferred_alternative_room',
            ),
        }),
        ('Proposed slot', {
            'fields': ('proposed_date', 'proposed_start_time', 'proposed_end_time'),
        }),
        ('Review', {
            'fields': ('review_notes', 'reviewed_by', 'reviewed_at',
                       'alternative_room_selected', 'alternative_room_notes'),
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at'),
        }),
        ('UniTime confirmation', {
            'fields': ('unitime_confirmed_by', 'unitime_confirmed_at', 'unitime_confirmation_note'),
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'created_at', 'updated_at'),
        }),
    )

    # Fields that only the workflow methods may change.
    workflow_fields = (
        'status',
        'reviewed_by', 'reviewed_at',
        'approved_by', 'approved_at',
        'unitime_confirmed_by', 'unitime_confirmed_at',
        'submitted_at', 'created_at', 'updated_at',
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.workflow_fields)
        if obj is not None:
            # The requester and programme should not change after submission.
            readonly += ['requester', 'programme']
        return readonly

    # -- actions: these call the model's workflow methods ------------------

    actions = ('action_start_review', 'action_approve', 'action_reject', 'action_confirm_in_unitime')

    def _run(self, request, queryset, method_name, success_label):
        done = 0
        for obj in queryset:
            try:
                getattr(obj, method_name)(request.user)
                done += 1
            except ValidationError as exc:
                self.message_user(
                    request, f'"{obj}": {" ".join(exc.messages)}', level=messages.ERROR
                )
        if done:
            self.message_user(request, f'{done} request(s) {success_label}.', level=messages.SUCCESS)

    @admin.action(description='Start review of selected requests')
    def action_start_review(self, request, queryset):
        self._run(request, queryset, 'start_review', 'moved to review')

    @admin.action(description='Approve selected requests')
    def action_approve(self, request, queryset):
        self._run(request, queryset, 'approve', 'approved')

    @admin.action(description='Reject selected requests (uses the saved review notes)')
    def action_reject(self, request, queryset):
        done = 0
        for obj in queryset:
            try:
                obj.reject(request.user, note=obj.review_notes)
                done += 1
            except ValidationError as exc:
                self.message_user(
                    request, f'"{obj}": {" ".join(exc.messages)}', level=messages.ERROR
                )
        if done:
            self.message_user(request, f'{done} request(s) rejected.', level=messages.SUCCESS)

    @admin.action(description='Confirm selected requests as updated in UniTime')
    def action_confirm_in_unitime(self, request, queryset):
        self._run(request, queryset, 'confirm_in_unitime', 'confirmed in UniTime')


@admin.register(TimetableRequestHistory)
class TimetableRequestHistoryAdmin(admin.ModelAdmin):
    """Audit log: view only."""

    list_display = ('created_at', 'request', 'action', 'old_status', 'new_status', 'performed_by')
    list_filter = ('action', 'new_status')
    search_fields = ('request__title_or_subject', 'performed_by__username', 'note')
    date_hierarchy = 'created_at'
    list_select_related = ('request', 'performed_by')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False