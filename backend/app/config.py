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



def parse_demo_mode(value: str) -> str:
    """Turn the DEMO_MODE setting into "off", "readonly" or "sandbox".

    off       the normal app (the default)
    readonly  public demo: purchases can't be added, edited or deleted
    sandbox   public demo: anyone can change purchases, within limits
    "true" means readonly, and so does any unrecognised value, as the safe choice.
    """
    value = value.strip().lower()
    if value in ("", "0", "false", "no", "off"):
        return "off"
    if value == "sandbox":
        return "sandbox"
    return "readonly"


DEMO_MODE = parse_demo_mode(os.getenv("DEMO_MODE", ""))
