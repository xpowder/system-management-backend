DEV_SECRET = "dev-only-change-this-secret"


def production_misconfigurations(debug, secret_key, allowed_hosts, testing=False):
    """Return blocking problems for a public/production process."""
    if testing or debug:
        return []
    errors = []
    secret = (secret_key or "").strip()
    if not secret or secret == DEV_SECRET or len(secret) < 32:
        errors.append(
            "DJANGO_SECRET_KEY must be a unique value of at least 32 characters "
            "when DJANGO_DEBUG=False."
        )
    if not allowed_hosts:
        errors.append("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=False.")
    return errors
