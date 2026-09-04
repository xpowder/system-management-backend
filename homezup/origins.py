"""CORS / CSRF / cookie helpers for the production frontend origin."""
from urllib.parse import urlparse


def merge_frontend_origin(allowed_hosts, cors_origins, frontend_origin):
    """Add the deployed frontend origin to hosts and CORS lists."""
    origin = (frontend_origin or "").strip().rstrip("/")
    hosts = list(allowed_hosts)
    cors = list(cors_origins)
    if not origin:
        return hosts, cors
    if origin not in cors:
        cors.append(origin)
    host = urlparse(origin).hostname
    if host and host not in hosts:
        hosts.append(host)
    return hosts, cors


def uses_cross_site_cookies(frontend_origin, public_domain=""):
    """True when the browser UI and API are on different hosts."""
    frontend_host = urlparse((frontend_origin or "").strip()).hostname or ""
    self_host = (public_domain or "").strip()
    if not frontend_host:
        return False
    if not self_host:
        return True
    return frontend_host != self_host
