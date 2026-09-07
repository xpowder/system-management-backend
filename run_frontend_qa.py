"""Launch Django against an isolated local SQLite QA database.

Never uses Railway / production Postgres.
Safe to run from the backend project root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def clear_remote_db_env() -> None:
    for key in (
        "DATABASE_URL",
        "DATABASE_PRIVATE_URL",
        "DATABASE_PUBLIC_URL",
        "PGHOST",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGPORT",
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_PUBLIC_DOMAIN",
        "RAILWAY_PRIVATE_DOMAIN",
        "HOMEZUP_TEST_DATABASE_URL",
    ):
        os.environ[key] = ""
    os.environ["DJANGO_DEBUG"] = "True"
    os.environ["DJANGO_HTTPS"] = "False"
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
    os.environ.setdefault(
        "DJANGO_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000",
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homezup.settings")


def patch_sqlite_path(db_name: str = "db_frontend_qa.sqlite3") -> Path:
    import homezup.database as dbmod

    base = Path(__file__).resolve().parent
    target = base / db_name

    def sqlite_database(base_dir: Path) -> dict:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": target,
            "OPTIONS": {
                "timeout": 20,
                "transaction_mode": "IMMEDIATE",
            },
        }

    dbmod.sqlite_database = sqlite_database  # type: ignore[method-assign]
    return target


def print_safe_target(db_path: Path) -> None:
    print("Environment: LOCAL QA")
    print("Database: SQLite")
    print("Host: (file)")
    print("Port: (n/a)")
    print(f"Database: {db_path.name}")
    print("Label: homezup_frontend_qa")


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    clear_remote_db_env()
    db_path = patch_sqlite_path()
    print_safe_target(db_path)

    # Import Django only after env + sqlite patch.
    from django.core.management import execute_from_command_line

    if not argv:
        argv = ["runserver", "127.0.0.1:8000"]
    execute_from_command_line(["manage.py", *argv])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
