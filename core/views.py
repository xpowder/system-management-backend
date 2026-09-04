from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect


def _safe_dist_file(relative: str) -> Path:
    dist = Path(settings.FRONTEND_DIST).resolve()
    target = (dist / relative).resolve()
    if target != dist and dist not in target.parents:
        raise Http404("Invalid path")
    if not target.is_file():
        raise Http404("File not found")
    return target


def healthz(request):
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")


def spa_index(request, rest=""):
    index = Path(settings.FRONTEND_DIST) / "index.html"
    if index.is_file():
        return FileResponse(index.open("rb"), content_type="text/html")
    origin = (getattr(settings, "FRONTEND_ORIGIN", "") or "").rstrip("/")
    if origin:
        return redirect(origin)
    return HttpResponse(
        "FlexOper frontend is not built yet.\n\n"
        "Daily use: open http://localhost:5173 after npm run dev.\n"
        "One-port delivery: cd frontend && npm run build, then refresh this page.\n",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


def frontend_asset(request, path):
    return FileResponse(_safe_dist_file(f"assets/{path}").open("rb"))


def frontend_root_file(request, filename):
    return FileResponse(_safe_dist_file(filename).open("rb"))


def media_file(request, path):
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise Http404("Invalid path")
    if not target.is_file():
        raise Http404("File not found")
    return FileResponse(target.open("rb"))
