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


def railway_runtime_hosts(public_domain="", private_domain=""):
    """Explicit hosts Railway uses for the public URL and in-container healthchecks.

    Do not use '*' or leading-dot wildcards. Railway healthchecks often send
    Host: localhost or 127.0.0.1; omitting those makes /healthz return 400
    and the platform shows 'Application failed to respond'.
    """
    hosts = []
    for host in (
        (public_domain or "").strip(),
        (private_domain or "").strip(),
        "localhost",
        "127.0.0.1",
        "healthcheck.railway.app",
        "backend-production-88cc.up.railway.app",
    ):
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def uses_cross_site_cookies(frontend_origin, public_domain=""):
    """True when the browser UI and API are on different hosts."""
    frontend_host = urlparse((frontend_origin or "").strip()).hostname or ""
    self_host = (public_domain or "").strip()
    if not frontend_host:
        return False
    if not self_host:
        return True
    return frontend_host != self_host
