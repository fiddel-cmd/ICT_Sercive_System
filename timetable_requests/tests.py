import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import (
    Programme,
    Room,
    StaffProgrammeAssignment,
    TimetableRequest,
    TimetableRequestHistory,
)

User = get_user_model()


class BaseTimetableTestCase(TestCase):
    """Shared fixtures: two users, a programme and a room."""

    def setUp(self):
        self.user = User.objects.create_user(username='lecturer1', password='secret12345')
        self.manager = User.objects.create_user(username='manager1', password='secret12345')
        self.programme = Programme.objects.create(code='CS', name='Computer Science')
        self.room = Room.objects.create(
            code='A-101',
            name='Lecture Hall A',
            building='Main Block',
            capacity=60,
        )
        self.other_room = Room.objects.create(code='B-202', name='Lab B', building='Tech Block', capacity=40)

    def make_request(self, **overrides):
        data = dict(
            programme=self.programme,
            requester=self.user,
            request_type=TimetableRequest.REQUEST_TYPE_ROOM_CHANGE,
            title_or_subject='Room change for CS101 lecture',
            course_code='CS101',
            course_name='Introduction to Programming',
            lecture_date=datetime.date(2026, 11, 20),
            lecture_start_time=datetime.time(9, 0),
            lecture_end_time=datetime.time(10, 30),
            original_room=self.room,
            reason='The assigned room is too small for the class size.',
        )
        data.update(overrides)
        return TimetableRequest.objects.create(**data)


# ---------------------------------------------------------------------------
# View smoke tests
# ---------------------------------------------------------------------------

class TimetableRequestsSmokeTests(BaseTimetableTestCase):
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


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TimetableRequestValidationTests(BaseTimetableTestCase):
    def test_lecture_end_must_be_after_start(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_request(lecture_end_time=datetime.time(8, 0))
        self.assertIn('lecture_end_time', ctx.exception.message_dict)

    def test_makeup_class_requires_proposed_slot(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_request(request_type=TimetableRequest.REQUEST_TYPE_MAKEUP_CLASS)
        errors = ctx.exception.message_dict
        self.assertIn('proposed_date', errors)
        self.assertIn('proposed_start_time', errors)
        self.assertIn('proposed_end_time', errors)

    def test_makeup_class_with_valid_slot_is_saved(self):
        request = self.make_request(
            request_type=TimetableRequest.REQUEST_TYPE_MAKEUP_CLASS,
            proposed_date=datetime.date(2026, 11, 27),
            proposed_start_time=datetime.time(14, 0),
            proposed_end_time=datetime.time(15, 30),
        )
        self.assertIsNotNone(request.pk)

    def test_partial_proposed_slot_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_request(proposed_date=datetime.date(2026, 11, 27))

    def test_proposed_end_must_be_after_start(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_request(
                request_type=TimetableRequest.REQUEST_TYPE_MAKEUP_CLASS,
                proposed_date=datetime.date(2026, 11, 27),
                proposed_start_time=datetime.time(15, 0),
                proposed_end_time=datetime.time(14, 0),
            )
        self.assertIn('proposed_end_time', ctx.exception.message_dict)

    def test_updated_at_changes_on_save(self):
        request = self.make_request()
        first = request.updated_at
        request.course_name = 'Programming Fundamentals'
        request.save()
        request.refresh_from_db()
        self.assertGreater(request.updated_at, first)


# ---------------------------------------------------------------------------
# Workflow and history
# ---------------------------------------------------------------------------

class TimetableRequestWorkflowTests(BaseTimetableTestCase):
    def test_creation_logs_submitted_history(self):
        request = self.make_request()
        entries = list(request.history.all())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].action, TimetableRequestHistory.ACTION_SUBMITTED)
        self.assertEqual(entries[0].performed_by, self.user)
        self.assertEqual(entries[0].new_status, TimetableRequest.STATUS_PENDING_REVIEW)

    def test_full_happy_path(self):
        request = self.make_request()

        request.start_review(self.manager)
        self.assertEqual(request.status, TimetableRequest.STATUS_UNDER_REVIEW)
        self.assertEqual(request.reviewed_by, self.manager)
        self.assertIsNotNone(request.reviewed_at)

        request.approve(self.manager)
        self.assertEqual(request.status, TimetableRequest.STATUS_APPROVED_PENDING_UPDATE)
        self.assertEqual(request.approved_by, self.manager)
        self.assertIsNotNone(request.approved_at)

        request.confirm_in_unitime(self.manager, note='Updated in UniTime.')
        self.assertEqual(request.status, TimetableRequest.STATUS_CONFIRMED_IN_UNITIME)
        self.assertEqual(request.unitime_confirmed_by, self.manager)

        request.refresh_from_db()
        self.assertEqual(request.status, TimetableRequest.STATUS_CONFIRMED_IN_UNITIME)

        actions = list(request.history.values_list('action', flat=True))
        self.assertEqual(
            actions,
            [
                TimetableRequestHistory.ACTION_SUBMITTED,
                TimetableRequestHistory.ACTION_REVIEW_STARTED,
                TimetableRequestHistory.ACTION_APPROVED,
                TimetableRequestHistory.ACTION_UNITIME_UPDATE_CONFIRMED,
            ],
        )

    def test_history_records_old_and_new_status(self):
        request = self.make_request()
        request.start_review(self.manager)
        entry = request.history.get(action=TimetableRequestHistory.ACTION_REVIEW_STARTED)
        self.assertEqual(entry.old_status, TimetableRequest.STATUS_PENDING_REVIEW)
        self.assertEqual(entry.new_status, TimetableRequest.STATUS_UNDER_REVIEW)
        self.assertEqual(entry.performed_by, self.manager)

    def test_cannot_skip_review(self):
        request = self.make_request()
        with self.assertRaises(ValidationError):
            request.approve(self.manager)

        request.refresh_from_db()
        self.assertEqual(request.status, TimetableRequest.STATUS_PENDING_REVIEW)
        self.assertEqual(request.history.count(), 1)

    def test_cannot_confirm_before_approval(self):
        request = self.make_request()
        request.start_review(self.manager)
        with self.assertRaises(ValidationError):
            request.confirm_in_unitime(self.manager)

    def test_direct_illegal_status_change_is_blocked(self):
        request = self.make_request()
        request.status = TimetableRequest.STATUS_CONFIRMED_IN_UNITIME
        with self.assertRaises(ValidationError):
            request.save()

    def test_terminal_states_have_no_exit(self):
        request = self.make_request()
        request.start_review(self.manager)
        request.reject(self.manager, note='Clashes with an exam.')
        with self.assertRaises(ValidationError):
            request.start_review(self.manager)

    def test_reject_requires_reason(self):
        request = self.make_request()
        request.start_review(self.manager)

        with self.assertRaises(ValidationError):
            request.reject(self.manager, note='')

        request.refresh_from_db()
        self.assertEqual(request.status, TimetableRequest.STATUS_UNDER_REVIEW)

    def test_reject_with_reason_succeeds(self):
        request = self.make_request()
        request.start_review(self.manager)
        request.reject(self.manager, note='No rooms available at that time.')

        request.refresh_from_db()
        self.assertEqual(request.status, TimetableRequest.STATUS_REJECTED)
        self.assertEqual(request.review_notes, 'No rooms available at that time.')

    def test_clarification_cycle(self):
        request = self.make_request()
        request.start_review(self.manager)
        request.request_clarification(self.manager, note='Which group is affected?')
        self.assertEqual(request.status, TimetableRequest.STATUS_NEEDS_CLARIFICATION)

        request.receive_clarification(self.user, note='Year 2 group B.')
        self.assertEqual(request.status, TimetableRequest.STATUS_UNDER_REVIEW)

    def test_clarification_request_needs_a_note(self):
        request = self.make_request()
        request.start_review(self.manager)
        with self.assertRaises(ValidationError):
            request.request_clarification(self.manager, note='   ')

    def test_only_requester_can_cancel(self):
        request = self.make_request()
        with self.assertRaises(ValidationError):
            request.cancel(self.manager)

        request.cancel(self.user, note='No longer needed.')
        self.assertEqual(request.status, TimetableRequest.STATUS_CANCELLED)

    def test_select_alternative_room_logs_history_without_status_change(self):
        request = self.make_request()
        request.start_review(self.manager)

        request.select_alternative_room(self.other_room, self.manager, notes='Closest free room.')

        request.refresh_from_db()
        self.assertEqual(request.alternative_room_selected, self.other_room)
        self.assertEqual(request.status, TimetableRequest.STATUS_UNDER_REVIEW)

        entry = request.history.get(action=TimetableRequestHistory.ACTION_ROOM_SELECTED)
        self.assertEqual(entry.old_status, entry.new_status)

    def test_cannot_select_room_before_review(self):
        request = self.make_request()
        with self.assertRaises(ValidationError):
            request.select_alternative_room(self.other_room, self.manager)

    def test_history_entries_are_append_only(self):
        request = self.make_request()
        entry = request.history.get()
        entry.note = 'tampered'
        with self.assertRaises(ValidationError):
            entry.save()


# ---------------------------------------------------------------------------
# Other models
# ---------------------------------------------------------------------------

class StaffProgrammeAssignmentTests(BaseTimetableTestCase):
    def test_same_role_cannot_be_assigned_twice(self):
        from django.db import IntegrityError, transaction

        StaffProgrammeAssignment.objects.create(
            user=self.manager,
            programme=self.programme,
            role=StaffProgrammeAssignment.ROLE_TIMETABLE_MANAGER,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffProgrammeAssignment.objects.create(
                user=self.manager,
                programme=self.programme,
                role=StaffProgrammeAssignment.ROLE_TIMETABLE_MANAGER,
            )

    def test_user_can_hold_different_roles_on_same_programme(self):
        StaffProgrammeAssignment.objects.create(
            user=self.manager, programme=self.programme, role=StaffProgrammeAssignment.ROLE_LECTURER
        )
        StaffProgrammeAssignment.objects.create(
            user=self.manager,
            programme=self.programme,
            role=StaffProgrammeAssignment.ROLE_TIMETABLE_MANAGER,
        )
        self.assertEqual(self.manager.programme_assignments.count(), 2)


# ---------------------------------------------------------------------------
# Admin smoke tests (these also confirm the admin config passes its checks)
# ---------------------------------------------------------------------------

class AdminSmokeTests(BaseTimetableTestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create_superuser(
            username='admin1', email='admin@example.com', password='secret12345'
        )
        self.client.force_login(self.admin_user)
        self.request_obj = self.make_request()

    def test_changelist_pages_load(self):
        for model in ('programme', 'room', 'staffprogrammeassignment', 'timetablerequest', 'timetablerequesthistory'):
            with self.subTest(model=model):
                response = self.client.get(reverse(f'admin:timetable_requests_{model}_changelist'))
                self.assertEqual(response.status_code, 200)

    def test_request_change_page_loads(self):
        response = self.client.get(
            reverse('admin:timetable_requests_timetablerequest_change', args=[self.request_obj.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_history_admin_is_view_only(self):
        response = self.client.get(reverse('admin:timetable_requests_timetablerequesthistory_add'))
        self.assertEqual(response.status_code, 403)

    def test_start_review_action_updates_status_and_history(self):
        response = self.client.post(
            reverse('admin:timetable_requests_timetablerequest_changelist'),
            {
                'action': 'action_start_review',
                '_selected_action': [self.request_obj.pk],
            },
        )
        self.assertEqual(response.status_code, 302)

        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, TimetableRequest.STATUS_UNDER_REVIEW)
        self.assertTrue(
            self.request_obj.history.filter(action=TimetableRequestHistory.ACTION_REVIEW_STARTED).exists()
        )