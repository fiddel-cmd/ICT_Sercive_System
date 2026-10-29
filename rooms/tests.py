from django.test import TestCase
from django.urls import reverse

from .models import StudyRoom


class StudyRoomListTests(TestCase):
    def test_homepage_shows_the_study_room_directory(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Study rooms')

    def test_room_list_shows_active_rooms(self):
        StudyRoom.objects.create(
            name='North Study Room',
            location='North Wing',
            capacity=12,
        )

        response = self.client.get(reverse('study_room_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'North Study Room')
        self.assertContains(response, 'North Wing')
        self.assertContains(response, '12')

    def test_room_list_hides_inactive_rooms(self):
        StudyRoom.objects.create(
            name='Closed Study Room',
            location='South Wing',
            capacity=8,
            is_active=False,
        )

        response = self.client.get(reverse('study_room_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Closed Study Room')


class LoginPageTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')
        self.assertContains(response, 'Register here')

    def test_register_page_renders(self):
        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register')
        self.assertContains(response, 'Back to login')
