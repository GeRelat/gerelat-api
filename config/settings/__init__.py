import os

env = os.getenv("DJANGO_ENV", "dev").lower()

if env in {"prod", "production"}:
    from .prod import *  # noqa: F403
else:
    from .dev import *  # noqa: F403
