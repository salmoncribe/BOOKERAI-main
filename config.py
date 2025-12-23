# config.py
import os
import json
from typing import Optional, Dict, Any


class Settings:
    """
    Central place for environment-configured settings.
    Keep defaults aligned with sheets.py.
    """

    # Google Sheets
    SHEET_ID: Optional[str] = os.getenv("SHEET_ID")
    SHEET_NAME: str = os.getenv("SHEET_NAME", "Barbers")
    HOURS_SHEET: str = os.getenv("HOURS_SHEET", "Hours")
    APPT_SHEET: str = os.getenv("APPT_SHEET", "Appointments")

    # Flask secret key (used by app.py; can also be set there)
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")

    # Auth options (sheets.py also reads these directly; exposing here can help for debugging)
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    SECRET_GCP_SA_RAW: Optional[str] = os.getenv("SECRET_GCP_SA")  # JSON string for a service account

    # Quality-of-life
    PYTHONDONTWRITEBYTECODE: str = os.getenv("PYTHONDONTWRITEBYTECODE", "1")  # avoid .pyc in containers

    @classmethod
    def validate(cls) -> None:
        """Raise a clear error early if critical config is missing."""
        if not cls.SHEET_ID:
            raise RuntimeError("SHEET_ID is required. Set it in your Cloud Run env vars.")
        # Not strictly required, but recommended:
        if not cls.SECRET_KEY:
            # You can let app.py generate a random one for dev,
            # but in production you should set SECRET_KEY.
            pass

    @classmethod
    def service_account_info(cls) -> Optional[Dict[str, Any]]:
        """Return parsed SA JSON if provided via SECRET_GCP_SA, else None."""
        if not cls.SECRET_GCP_SA_RAW:
            return None
        try:
            return json.loads(cls.SECRET_GCP_SA_RAW)
        except Exception:
            raise RuntimeError("SECRET_GCP_SA is set but not valid JSON.")


settings = Settings()
