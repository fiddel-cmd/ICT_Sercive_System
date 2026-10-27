from django.contrib import admin

from .models import StudyRoom


@admin.register(StudyRoom)
class StudyRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'location')
