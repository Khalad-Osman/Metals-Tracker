import os
from pathlib import Path

from dotenv import load_dotenv

# Read settings from backend/.env (if it exists) into environment variables.
# Real environment variables take priority over the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# SQLite file in the backend folder for now; set DATABASE_URL to use PostgreSQL later.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./metals.db")

# Key for metalpriceapi.com, used to download daily spot prices.
METALS_API_KEY = os.getenv("METALS_API_KEY", "")
