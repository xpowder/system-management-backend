import logging
import time

from django.middleware.csrf import get_token

logger = logging.getLogger("flexoper.request")


class EnsureCsrfCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        get_token(request)
        return self.get_response(request)


class RequestLogMiddleware:
    """Write each request to stdout so Railway Deploy Logs show API traffic."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip("/") == "/healthz":
            return self.get_response(request)
        started = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "%s %s %s %sms",
            request.method,
            request.get_full_path(),
            response.status_code,
            elapsed_ms,
        )
        return response
