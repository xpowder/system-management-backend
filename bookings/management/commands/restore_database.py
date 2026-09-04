"""Restore the local SQLite database from a backup file."""
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Restore db.sqlite3 from a backup created by backup_database. "
        "Stop the local server before restoring."
    )

    def add_arguments(self, parser):
        parser.add_argument("backup_file", type=str)
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite the live database without extra confirmation output.",
        )

    def handle(self, *args, **options):
        engine = settings.DATABASES["default"]["ENGINE"]
        if "sqlite3" not in engine:
            raise CommandError("restore_database currently supports SQLite only.")

        backup_path = Path(options["backup_file"])
        if not backup_path.exists():
            raise CommandError(f"Backup file not found: {backup_path}")

        db_path = Path(settings.DATABASES["default"]["NAME"])
        db_path.parent.mkdir(parents=True, exist_ok=True)

        source = sqlite3.connect(str(backup_path))
        try:
            destination = sqlite3.connect(str(db_path))
            with destination:
                source.backup(destination)
            destination.close()
        finally:
            source.close()

        self.stdout.write(self.style.SUCCESS(f"Restored database from {backup_path}"))
