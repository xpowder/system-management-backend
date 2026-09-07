"""Backup the configured database. SQLite uses the backup API; PostgreSQL uses pg_dump."""
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from homezup.pg_tools import find_pg_executable


class Command(BaseCommand):
    help = (
        "Backup the configured database. SQLite writes a .sqlite3 file. "
        "PostgreSQL writes a pg_dump custom-format file (.dump). "
        "This command never deletes or overwrites production data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-dir",
            type=str,
            default=None,
            help="Directory to save backups (default: settings.BACKUP_DIR)",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help="After writing the file, verify it can be opened (sqlite) or listed (pg_restore -l).",
        )

    def handle(self, *args, **options):
        engine = settings.DATABASES["default"]["ENGINE"]
        backup_dir = Path(
            options.get("backup_dir")
            or getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups")
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

        if "sqlite3" in engine:
            backup_path = self._backup_sqlite(backup_dir, timestamp)
        elif "postgresql" in engine:
            backup_path = self._backup_postgres(backup_dir, timestamp)
        else:
            raise CommandError(f"Unsupported database engine: {engine}")

        self.stdout.write(self.style.SUCCESS(f"Database backed up to {backup_path}"))
        self.stdout.write(f"Size: {backup_path.stat().st_size / 1024:.2f} KB")
        if options["verify"]:
            self._verify(backup_path, engine)
            self.stdout.write(self.style.SUCCESS("Backup file verified."))
        if "postgresql" in engine:
            self.stdout.write(
                "Restore into a STAGING database only: "
                f"python manage.py restore_database {backup_path} --target-database homezup_restore_test"
            )
        else:
            self.stdout.write(
                "Restore: python manage.py restore_database "
                f"{backup_path} --destination backups/restore_test.sqlite3"
            )

    def _backup_sqlite(self, backup_dir, timestamp):
        name = str(settings.DATABASES["default"]["NAME"])
        backup_path = backup_dir / f"homezup_{timestamp}.sqlite3"
        uri = name.startswith("file:") or name == ":memory:" or "mode=memory" in name
        if not uri and not Path(name).exists():
            raise CommandError(f"Database not found at {name}")
        source = sqlite3.connect(name, uri=uri)
        try:
            destination = sqlite3.connect(str(backup_path))
            with destination:
                source.backup(destination)
            destination.close()
        finally:
            source.close()
        return backup_path

    def _backup_postgres(self, backup_dir, timestamp):
        db = settings.DATABASES["default"]
        pg_dump = find_pg_executable("pg_dump")
        if not pg_dump:
            raise CommandError(
                "pg_dump was not found on PATH or in PostgreSQL's bin directory. "
                "Install PostgreSQL client tools, or set HOMEZUP_PG_BIN."
            )
        backup_path = backup_dir / f"homezup_{timestamp}.dump"
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = str(db["PASSWORD"])
        command = [
            pg_dump,
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(backup_path),
            "--host",
            str(db.get("HOST") or "localhost"),
            "--port",
            str(db.get("PORT") or "5432"),
            "--username",
            str(db.get("USER") or "postgres"),
            "--dbname",
            str(db["NAME"]),
        ]
        completed = subprocess.run(command, env=env, capture_output=True, text=True)
        if completed.returncode != 0:
            if backup_path.exists():
                backup_path.unlink()
            raise CommandError(f"pg_dump failed: {completed.stderr.strip() or completed.stdout.strip()}")
        return backup_path

    def _verify(self, backup_path, engine):
        if "sqlite3" in engine:
            connection = sqlite3.connect(str(backup_path))
            try:
                tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
                ).fetchall()
                if not tables:
                    raise CommandError("SQLite backup verification failed: no tables found.")
            finally:
                connection.close()
            return
        pg_restore = find_pg_executable("pg_restore")
        if not pg_restore:
            raise CommandError("Backup written, but pg_restore is missing so the dump could not be listed.")
        completed = subprocess.run(
            [pg_restore, "--list", str(backup_path)],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise CommandError(f"pg_restore --list failed: {completed.stderr.strip()}")
