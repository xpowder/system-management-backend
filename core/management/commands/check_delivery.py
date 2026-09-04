from pathlib import Path
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check whether FlexOper is ready to hand over to the gym."

    def handle(self, *args, **options):
        errors = []
        warnings = []
        testing = "test" in sys.argv

        if settings.SECRET_KEY == "dev-only-change-this-secret" and not settings.DEBUG and not testing:
            errors.append("DJANGO_SECRET_KEY is still the development default.")

        if not settings.DEBUG and not testing:
            static_root = Path(settings.STATIC_ROOT)
            if not static_root.exists() or not any(static_root.iterdir()):
                errors.append("Static files are not collected. Run: python manage.py collectstatic --noinput")

        if "127.0.0.1" not in settings.ALLOWED_HOSTS and "localhost" not in settings.ALLOWED_HOSTS:
            warnings.append("ALLOWED_HOSTS does not include localhost. Fine for a public domain, not for this PC.")

        index = settings.FRONTEND_DIST / "index.html"
        if not index.is_file():
            warnings.append(
                "Frontend is not built (frontend/dist/index.html missing). "
                "Daily use: npm run dev on port 5173. One-port use: cd frontend && npm run build."
            )

        User = get_user_model()
        if (
            not testing
            and not User.objects.filter(is_staff=True).exists()
            and not User.objects.filter(is_superuser=True).exists()
        ):
            errors.append("No staff user exists. Create one with: python manage.py createsuperuser")

        db_name = str(settings.DATABASES["default"]["NAME"])
        engine = settings.DATABASES["default"]["ENGINE"]
        if "postgresql" in engine:
            self.stdout.write(f"Database: PostgreSQL ({db_name})")
        elif (
            "sqlite3" in engine
            and ":memory:" not in db_name
            and "mode=memory" not in db_name
            and not Path(db_name).exists()
        ):
            warnings.append("SQLite database file was not found yet. Run: python manage.py migrate")

        if settings.DEBUG:
            warnings.append("DEBUG is True. That is OK on this gym PC. Set DJANGO_DEBUG=False before putting it on the internet.")

        for item in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {item}"))
        for item in errors:
            self.stdout.write(self.style.ERROR(f"ERROR: {item}"))

        if errors:
            raise CommandError("Delivery check failed. Fix the errors above.")

        self.stdout.write(self.style.SUCCESS("Delivery check passed."))
        self.stdout.write("Open the gym app at http://127.0.0.1:8000 (built frontend) or http://localhost:5173 (dev).")
        engine = settings.DATABASES["default"]["ENGINE"]
        if "sqlite3" in engine:
            self.stdout.write("Backup: python manage.py backup_database")
            self.stdout.write("Restore: python manage.py restore_database backups/<file>.sqlite3")
        else:
            self.stdout.write("PostgreSQL backups are handled by the database host (Railway Postgres).")
