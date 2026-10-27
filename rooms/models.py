from django.core.validators import MinValueValidator
from django.db import models


class StudyRoom(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'study room'
        verbose_name_plural = 'study rooms'

    def __str__(self):
        return self.name
