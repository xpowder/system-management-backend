"""Production HTTP bind address. Railway injects PORT; never hardcode it."""
import os


class MissingPort(RuntimeError):
    """Raised when Railway (or another host) did not provide PORT."""


def wsgi_bind_host_port():
    """Return (host, port) for the WSGI server.

    Railway and Docker Compose must set PORT. The value is read from the
    environment at runtime so this never hardcodes 8000/8080/etc.
    """
    port = (os.environ.get("PORT") or "").strip()
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"):
        if not port:
            raise MissingPort(
                "PORT is not set. Railway injects PORT automatically. "
                "Delete any custom PORT variable so the platform value is used."
            )
        return "0.0.0.0", int(port)
    if port:
        return "0.0.0.0", int(port)
    from decouple import config

    listen = config("DJANGO_LISTEN", default="0.0.0.0:8000")
    host, separator, listen_port = listen.rpartition(":")
    if not separator:
        host, listen_port = "0.0.0.0", listen
    return host or "0.0.0.0", int(listen_port or 8000)


def gunicorn_argv():
    """Gunicorn CLI for homezup.wsgi, bound to 0.0.0.0:$PORT on Railway."""
    host, port = wsgi_bind_host_port()
    workers = (os.environ.get("WEB_CONCURRENCY") or "2").strip() or "2"
    return [
        "gunicorn",
        "homezup.wsgi:application",
        "--bind",
        f"{host}:{port}",
        "--workers",
        workers,
        "--threads",
        "2",
        "--timeout",
        "120",
        "--max-requests",
        "500",
        "--max-requests-jitter",
        "50",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
        "--capture-output",
    ]
