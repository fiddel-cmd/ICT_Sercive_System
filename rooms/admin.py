from django.contrib import admin

from timetable_requests.models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'building', 'capacity', 'is_active')
    list_filter = ('is_active', 'building')
    search_fields = ('code', 'name', 'building')
