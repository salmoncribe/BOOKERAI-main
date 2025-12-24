# config.py
import os
import json
from typing import Optional, Dict, Any


class Settings:
    """
    Central place for environment-configured settings.
    Keep defaults aligned with sheets.py.
    """

    # Flask secret key (used by app.py; can also be set there)
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")




settings = Settings()
