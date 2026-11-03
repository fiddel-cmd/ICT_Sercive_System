from django.contrib import admin

from .models import Programme, StaffProgrammeAssignment, TimetableRequest, TimetableRequestHistory


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(StaffProgrammeAssignment)
class StaffProgrammeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'programme', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'programme')
    search_fields = ('user__username', 'programme__code', 'programme__name')


@admin.register(TimetableRequest)
class TimetableRequestAdmin(admin.ModelAdmin):
    list_display = ('request_type', 'status', 'programme', 'requester', 'submitted_at')
    list_filter = ('status', 'request_type', 'programme')
    search_fields = ('title_or_subject', 'course_code', 'requester__username')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at')


@admin.register(TimetableRequestHistory)
class TimetableRequestHistoryAdmin(admin.ModelAdmin):
    list_display = ('request', 'action', 'old_status', 'new_status', 'performed_by', 'created_at')
    list_filter = ('action',)
    search_fields = ('request__title_or_subject', 'note')
