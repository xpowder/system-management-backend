"""Create a consistent SQLite backup of the local Homezup database."""
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Backup the local SQLite database using the SQLite backup API. "
        "Restore with: python manage.py restore_database backups/<file>.sqlite3"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-dir",
            type=str,
            default=None,
            help="Directory to save backups (default: settings.BACKUP_DIR)",
        )

    def handle(self, *args, **options):
        engine = settings.DATABASES["default"]["ENGINE"]
        if "sqlite3" not in engine:
            raise CommandError("backup_database currently supports SQLite only.")

        backup_dir = Path(
            options.get("backup_dir")
            or getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups")
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            raise CommandError(f"Database not found at {db_path}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_path = backup_dir / f"homezup_{timestamp}.sqlite3"

        source = sqlite3.connect(str(db_path))
        try:
            destination = sqlite3.connect(str(backup_path))
            with destination:
                source.backup(destination)
            destination.close()
        finally:
            source.close()

        self.stdout.write(self.style.SUCCESS(f"Database backed up to {backup_path}"))
        self.stdout.write(f"Size: {backup_path.stat().st_size / 1024:.2f} KB")
        self.stdout.write(
            "Restore: python manage.py restore_database "
            f"{backup_path}"
        )
