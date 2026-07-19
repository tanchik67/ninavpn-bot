from slowapi import Limiter
from slowapi.util import get_remote_address

from core.settings import saas_settings

limiter = Limiter(key_func=get_remote_address, default_limits=[saas_settings.API_RATE_LIMIT])
