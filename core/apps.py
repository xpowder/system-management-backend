from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from django.contrib import admin

        def _superuser_admin_only(request):
            user = getattr(request, "user", None)
            return bool(user and user.is_active and user.is_superuser)

        admin.site.has_permission = _superuser_admin_only
