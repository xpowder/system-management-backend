"""Database settings: SQLite locally, PostgreSQL when Railway (or any host) provides a URL."""
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

RAILWAY_INTERNAL_HOST = "railway.internal"
LOCAL_INTERNAL_DB_ERROR = (
    "This PC cannot reach postgres.railway.internal (that host only exists on Railway). "
    "In Railway open the Postgres service → Variables and copy DATABASE_PUBLIC_URL "
    "(host looks like *.proxy.rlwy.net) into DATABASE_PUBLIC_URL in your .env, then run migrate again."
)


def sqlite_database(base_dir: Path) -> dict:
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(base_dir) / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
        },
    }


def _needs_ssl(value: str) -> bool:
    """Require SSL only for public Railway (and similar) hosts, not Docker/local."""
    text = (value or "").lower()
    if any(
        token in text
        for token in (
            "railway.internal",
            "localhost",
            "127.0.0.1",
            "@db:",
            "@db/",
            "://db:",
        )
    ):
        return False
    return "rlwy.net" in text or "proxy.rlwy" in text


def _is_internal(value: str) -> bool:
    return RAILWAY_INTERNAL_HOST in (value or "").lower()


def pick_database_url(*, on_railway, database_url="", private_url="", public_url=""):
    """On this PC skip Railway private hosts; on Railway prefer the injected URL."""
    public_url = (public_url or "").strip()
    database_url = (database_url or "").strip()
    private_url = (private_url or "").strip()
    if on_railway:
        return database_url or private_url or public_url
    for url in (public_url, database_url, private_url):
        if url and not _is_internal(url):
            return url
    return public_url or database_url or private_url


def postgres_database_from_url(database_url: str) -> dict:
    import dj_database_url

    use_ssl = _needs_ssl(database_url)
    config = dj_database_url.parse(
        database_url,
        conn_max_age=0 if use_ssl else 600,
        conn_health_checks=True,
        ssl_require=use_ssl,
    )
    options = dict(config.get("OPTIONS") or {})
    if use_ssl:
        options.setdefault("sslmode", "require")
        options.update(
            {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
                "connect_timeout": 15,
            }
        )
    config["OPTIONS"] = options
    return config


def postgres_database_from_parts(*, name, user, password, host, port) -> dict:
    host = (host or "").strip()
    sslmode = "require" if _needs_ssl(host) else "prefer"
    options = {"sslmode": sslmode}
    if sslmode == "require":
        options.update(
            {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
                "connect_timeout": 15,
            }
        )
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": str(port or "5432"),
        "CONN_MAX_AGE": 0 if sslmode == "require" else 600,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }


def build_databases(
    base_dir,
    *,
    testing=False,
    on_railway=False,
    database_url="",
    private_url="",
    public_url="",
    pg_name="",
    pg_user="",
    pg_password="",
    pg_host="",
    pg_port="5432",
):
    """Prefer a URL (Railway DATABASE_URL), then PG* vars, else local SQLite.

    Tests always use SQLite so a production DATABASE_URL in the environment
    cannot point unit tests at Railway.
    """
    if testing:
        return {"default": sqlite_database(base_dir)}

    url = pick_database_url(
        on_railway=on_railway,
        database_url=database_url,
        private_url=private_url,
        public_url=public_url,
    )
    if url:
        if not on_railway and _is_internal(url):
            raise ImproperlyConfigured(LOCAL_INTERNAL_DB_ERROR)
        return {"default": postgres_database_from_url(url)}

    host = (pg_host or "").strip()
    name = (pg_name or "").strip()
    if host and name:
        if not on_railway and _is_internal(host):
            raise ImproperlyConfigured(LOCAL_INTERNAL_DB_ERROR)
        return {
            "default": postgres_database_from_parts(
                name=name,
                user=pg_user or "postgres",
                password=pg_password or "",
                host=host,
                port=pg_port,
            )
        }

    return {"default": sqlite_database(base_dir)}
