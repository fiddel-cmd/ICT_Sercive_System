from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Programme, Room, TimetableRequest


class TimetableRequestsSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='lecturer1', password='secret12345')
        self.programme = Programme.objects.create(code='CS', name='Computer Science')
        self.room = Room.objects.create(
            code='A-101',
            name='Lecture Hall A',
            building='Main Block',
            capacity=60,
        )

    def test_create_request_page_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('timetable_request_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Submit timetable request')
        self.assertContains(response, 'Submit request')

    def test_create_request_saves_valid_submission(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('timetable_request_create'),
            {
                'programme': self.programme.pk,
                'request_type': TimetableRequest.REQUEST_TYPE_ROOM_CHANGE,
                'title_or_subject': 'Room change for CS101 lecture',
                'course_code': 'CS101',
                'course_name': 'Introduction to Programming',
                'lecture_date': '2026-11-20',
                'lecture_start_time': '09:00',
                'lecture_end_time': '10:30',
                'original_room': self.room.pk,
                'preferred_alternative_room': self.room.pk,
                'reason': 'The assigned room is too small for the class size.',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(TimetableRequest.objects.count(), 1)

        created_request = TimetableRequest.objects.get()
        self.assertEqual(created_request.requester, self.user)
        self.assertEqual(created_request.status, TimetableRequest.STATUS_PENDING_REVIEW)
        self.assertEqual(created_request.title_or_subject, 'Room change for CS101 lecture')
