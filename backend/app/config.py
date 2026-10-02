import os
from pathlib import Path

from dotenv import load_dotenv

# Read settings from backend/.env (if it exists) into environment variables.
# Real environment variables take priority over the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Which database to use. Without DATABASE_URL, a SQLite file in the backend folder.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./metals.db")

# Key for metals.dev, used to download daily spot prices.
METALS_DEV_API_KEY = os.getenv("METALS_DEV_API_KEY", "")

# Websites allowed to call this API from a browser, comma-separated.
# Locally that's the Vite dev server; when deployed, the frontend's address.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Public read-only demo: when true, purchases can't be added, edited or deleted.
DEMO_MODE = os.getenv("DEMO_MODE", "").strip().lower() in ("1", "true", "yes")
