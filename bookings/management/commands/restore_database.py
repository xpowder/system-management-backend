"""Restore a backup into a destination that is not the live database by default."""
import os
import sqlite3
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from homezup.pg_tools import find_pg_executable


class Command(BaseCommand):
    help = (
        "Restore a backup created by backup_database. "
        "Refuses to overwrite the configured live database unless you pass an explicit flag."
    )

    def add_arguments(self, parser):
        parser.add_argument("backup_file", type=str)
        parser.add_argument(
            "--destination",
            type=str,
            default="",
            help="SQLite destination file. Required unless overwriting the configured SQLite file.",
        )
        parser.add_argument(
            "--target-database",
            type=str,
            default="",
            help="PostgreSQL database name to restore into. Must not be the live name unless forced.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="SQLite: overwrite the destination file if it already exists.",
        )
        parser.add_argument(
            "--i-understand-this-overwrites-the-configured-database",
            action="store_true",
            dest="overwrite_configured",
            help="Dangerous. Allow restoring into the configured DATABASES['default'] name.",
        )

    def handle(self, *args, **options):
        backup_path = Path(options["backup_file"])
        if not backup_path.exists():
            raise CommandError(f"Backup file not found: {backup_path}")
        engine = settings.DATABASES["default"]["ENGINE"]
        suffix = backup_path.suffix.lower()
        if suffix in {".sqlite3", ".db"} or "sqlite3" in engine and suffix != ".dump":
            self._restore_sqlite(backup_path, options)
            return
        if suffix == ".dump" or "postgresql" in engine:
            self._restore_postgres(backup_path, options)
            return
        raise CommandError(f"Unrecognized backup file type: {backup_path}")

    def _restore_sqlite(self, backup_path, options):
        configured = Path(settings.DATABASES["default"]["NAME"])
        destination = Path(options["destination"]) if options["destination"] else configured
        if destination.resolve() == configured.resolve() and not options["overwrite_configured"]:
            raise CommandError(
                "Refusing to overwrite the configured SQLite database. "
                "Pass --destination path/to/restore-test.sqlite3, or "
                "--i-understand-this-overwrites-the-configured-database"
            )
        if destination.exists() and not options["force"] and destination.resolve() != configured.resolve():
            raise CommandError(f"Destination already exists: {destination}. Pass --force to overwrite it.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(backup_path))
        try:
            target = sqlite3.connect(str(destination))
            with target:
                source.backup(target)
            target.close()
        finally:
            source.close()
        self.stdout.write(self.style.SUCCESS(f"Restored SQLite backup into {destination}"))

    def _restore_postgres(self, backup_path, options):
        db = settings.DATABASES["default"]
        live_name = str(db["NAME"])
        target = (options["target_database"] or "").strip()
        if not target:
            raise CommandError(
                "Refusing to restore PostgreSQL without --target-database. "
                "Use a staging database name, never the live Railway database."
            )
        if target == live_name and not options["overwrite_configured"]:
            raise CommandError(
                f"Refusing to restore into the configured database '{live_name}'. "
                "Create/use a staging database and pass --target-database <staging_name>."
            )
        pg_restore = find_pg_executable("pg_restore")
        if not pg_restore:
            raise CommandError(
                "pg_restore was not found on PATH or in PostgreSQL's bin directory. "
                "Install PostgreSQL client tools, or set HOMEZUP_PG_BIN."
            )
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = str(db["PASSWORD"])
        command = [
            pg_restore,
            "--no-owner",
            "--no-acl",
            "--clean",
            "--if-exists",
            "--host",
            str(db.get("HOST") or "localhost"),
            "--port",
            str(db.get("PORT") or "5432"),
            "--username",
            str(db.get("USER") or "postgres"),
            "--dbname",
            target,
            str(backup_path),
        ]
        completed = subprocess.run(command, env=env, capture_output=True, text=True)
        if completed.returncode != 0:
            raise CommandError(f"pg_restore failed: {completed.stderr.strip() or completed.stdout.strip()}")
        self.stdout.write(self.style.SUCCESS(f"Restored PostgreSQL dump into database '{target}'"))
