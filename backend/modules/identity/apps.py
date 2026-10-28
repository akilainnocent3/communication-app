from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed_roles(sender, **kwargs):
    from .services import ensure_roles

    ensure_roles()


class IdentityConfig(AppConfig):
    name = "modules.identity"
    label = "identity"
    verbose_name = "Identity"

    def ready(self):
        import common.checks  # noqa: F401 - deploy checks (Redis roles)
        import common.schema  # noqa: F401 - registers the OpenAPI auth extension

        # No sender filter: runs after every app's migrations, so later apps' permissions are included.
        post_migrate.connect(_seed_roles, dispatch_uid="identity.seed_roles")
