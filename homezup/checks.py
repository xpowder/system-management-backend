DEV_SECRET = "dev-only-change-this-secret"


def debug_default(on_railway: bool) -> bool:
    """Railway must not boot with DEBUG=True just because DJANGO_DEBUG was omitted."""
    return not on_railway


def cache_settings(testing: bool, debug: bool) -> dict:
    """Login lockout must be shared across Gunicorn workers in production."""
    if testing or debug:
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "flexoper_cache",
        }
    }


def production_misconfigurations(debug, secret_key, allowed_hosts, testing=False):
    """Return blocking problems for a public/production process."""
    if testing or debug:
        return []
    errors = []
    secret = (secret_key or "").strip()
    if not secret or secret == DEV_SECRET or len(secret) < 32:
        errors.append(
            "DJANGO_SECRET_KEY must be a unique value of at least 32 characters "
            "when DJANGO_DEBUG=False. Do not use quotes, and do not use # "
            "(it truncates the value in many env editors)."
        )
    if not allowed_hosts:
        errors.append("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=False.")
    return errors
