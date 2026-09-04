from decouple import config
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Serve FlexOper with Waitress instead of Django's development server."

    def handle(self, *args, **options):
        from waitress import serve

        from homezup.wsgi import application

        railway_port = config("PORT", default="")
        if railway_port:
            host, port = "0.0.0.0", int(railway_port)
        else:
            listen = config("DJANGO_LISTEN", default="127.0.0.1:8000")
            host, separator, port = listen.rpartition(":")
            if not separator:
                host, port = "127.0.0.1", listen
            host = host or "127.0.0.1"
            port = int(port or 8000)
        self.stdout.write(self.style.SUCCESS(f"FlexOper production server: http://{host}:{port}"))
        serve(
            application,
            host=host,
            port=port,
            threads=8,
            ident="FlexOper",
            expose_tracebacks=False,
        )
