import os
import sys

from django.core.management.base import BaseCommand, CommandError

from homezup.bind import MissingPort, gunicorn_argv, wsgi_bind_host_port


class Command(BaseCommand):
    help = "Serve FlexOper with Gunicorn on 0.0.0.0:$PORT (Linux/Railway)."

    def handle(self, *args, **options):
        try:
            host, port = wsgi_bind_host_port()
        except MissingPort as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Listening at: http://{host}:{port}"))
        self.stdout.flush()
        if os.name == "nt":
            from wsgiref.simple_server import make_server

            from homezup.wsgi import application

            httpd = make_server(host, port, application)
            httpd.serve_forever()
            return
        argv = gunicorn_argv()
        os.execvp(argv[0], argv)
        sys.exit("gunicorn failed to start")
