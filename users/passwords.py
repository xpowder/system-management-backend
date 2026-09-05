"""Server-side password rules for staff APIs."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from ninja.errors import HttpError


def require_strong_password(password: str, user=None) -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise HttpError(400, " ".join(exc.messages))
