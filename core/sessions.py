"""Invalidate stolen sessions after a password change."""
from django.contrib.sessions.models import Session
from django.utils import timezone


def flush_user_sessions(user, keep_session_key=None) -> None:
    user_id = str(user.pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if keep_session_key and session.session_key == keep_session_key:
            continue
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == user_id:
            session.delete()
