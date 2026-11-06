"""Who may do what in the timetable request workflow.

All rules live here so models, admin, forms and views share one source of truth.
Every rule is based on an *active* StaffProgrammeAssignment for the request's
programme. Superusers are allowed everything.

This module imports models lazily (inside functions) because models.py imports it.
"""

from django.db.models import Q


def _roles():
    from .models import StaffProgrammeAssignment

    return StaffProgrammeAssignment


def _is_authenticated(user):
    return bool(user and getattr(user, 'is_authenticated', False))


def has_active_role(user, programme_id, roles):
    """True if the user holds one of `roles` on the programme via an active assignment."""
    if not _is_authenticated(user):
        return False
    return user.programme_assignments.filter(
        programme_id=programme_id, role__in=roles, is_active=True
    ).exists()


def _review_roles():
    A = _roles()
    return (A.ROLE_TIMETABLE_MANAGER, A.ROLE_PROGRAMME_ADMINISTRATOR)


# -- submitting --------------------------------------------------------------

def can_submit(user, programme):
    """A lecturer assigned to the programme may submit requests for it."""
    if not _is_authenticated(user):
        return False
    if user.is_superuser:
        return True
    return has_active_role(user, programme.pk, (_roles().ROLE_LECTURER,))


# -- reviewing ---------------------------------------------------------------

def can_review(user, timetable_request):
    """Start review, request clarification, select a room, approve or reject."""
    if not _is_authenticated(user):
        return False
    if user.is_superuser:
        return True
    return has_active_role(user, timetable_request.programme_id, _review_roles())


def can_approve(user, timetable_request):
    return can_review(user, timetable_request)


def can_confirm_in_unitime(user, timetable_request):
    """Only a timetable manager (not a programme administrator) updates UniTime."""
    if not _is_authenticated(user):
        return False
    if user.is_superuser:
        return True
    return has_active_role(
        user, timetable_request.programme_id, (_roles().ROLE_TIMETABLE_MANAGER,)
    )


# -- requester actions -------------------------------------------------------

def can_cancel(user, timetable_request):
    """Only the person who submitted the request may cancel it."""
    return _is_authenticated(user) and user.pk == timetable_request.requester_id


def can_respond_to_clarification(user, timetable_request):
    """The requester answers a clarification (reviewers may record it on their behalf)."""
    return can_cancel(user, timetable_request) or can_review(user, timetable_request)


# -- viewing -----------------------------------------------------------------

def can_view(user, timetable_request):
    return can_cancel(user, timetable_request) or can_review(user, timetable_request)


def visible_requests(user):
    """Requests this user may see: their own, plus those in programmes they review."""
    from .models import TimetableRequest

    queryset = TimetableRequest.objects.all()
    if not _is_authenticated(user):
        return queryset.none()
    if user.is_superuser:
        return queryset

    reviewed_programmes = user.programme_assignments.filter(
        is_active=True, role__in=_review_roles()
    ).values('programme_id')
    return queryset.filter(Q(requester=user) | Q(programme_id__in=reviewed_programmes))