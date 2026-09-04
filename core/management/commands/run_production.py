import os

from decouple import config
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Serve FlexOper with Waitress instead of Django's development server."

    def handle(self, *args, **options):
        from waitress import serve

        from homezup.wsgi import application

        on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
        port = os.environ.get("PORT") or config("PORT", default="")
        if on_railway or port:
            host = "0.0.0.0"
            port = int(port or "8000")
        else:
            listen = config("DJANGO_LISTEN", default="0.0.0.0:8000")
            host, separator, port = listen.rpartition(":")
            if not separator:
                host, port = "0.0.0.0", listen
            host = host or "0.0.0.0"
            port = int(port or 8000)
        self.stdout.write(self.style.SUCCESS(f"FlexOper production server: http://{host}:{port}"))
        self.stdout.write("Request logs go to stdout (Railway → service → Deployments → View logs).")
        serve(
            application,
            host=host,
            port=port,
            threads=8,
            ident="FlexOper",
            expose_tracebacks=False,
        )
