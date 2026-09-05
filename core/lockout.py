"""Login brute-force limits that expire and cannot permanently lock a desk."""
from django.core.cache import cache

ACCOUNT_LIMIT = 10
IP_LIMIT = 40
WINDOW_SECONDS = 15 * 60


def account_key(ip: str, username: str) -> str:
    return f"login-fail:{ip}:{(username or '').lower()}"


def ip_key(ip: str) -> str:
    return f"login-fail-ip:{ip}"


def _count(key: str) -> int:
    return int(cache.get(key) or 0)


def _incr(key: str) -> int:
    cache.add(key, 0, WINDOW_SECONDS)
    try:
        return int(cache.incr(key))
    except ValueError:
        cache.set(key, 1, WINDOW_SECONDS)
        return 1


def is_blocked(ip: str, username: str) -> bool:
    return _count(account_key(ip, username)) >= ACCOUNT_LIMIT or _count(ip_key(ip)) >= IP_LIMIT


def record_failure(ip: str, username: str) -> None:
    _incr(account_key(ip, username))
    _incr(ip_key(ip))


def clear_account_failures(ip: str, username: str) -> None:
    cache.delete(account_key(ip, username))
