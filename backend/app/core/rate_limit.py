"""slowapi-based rate limiter shared across routers."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# key_func uses the client IP resolved by Starlette (which respects
# uvicorn's --forwarded-allow-ips, so X-Forwarded-For from trusted proxies
# is honored while spoofing from untrusted networks is ignored).
#
# Disabled under APP_ENV=test so fixtures that create many sessions do not
# trip the limiter. Production behavior is unaffected.
_settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    enabled=_settings.APP_ENV != "test",
)

__all__ = ["limiter"]
