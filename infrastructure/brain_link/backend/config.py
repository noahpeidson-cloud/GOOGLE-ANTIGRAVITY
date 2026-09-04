import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# Load any .env present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

if not AUTH_TOKEN:
    # Check if a persistent token file exists
    token_file = BASE_DIR / ".auth_token"
    if token_file.exists():
        AUTH_TOKEN = token_file.read_text(encoding="utf-8").strip()
    else:
        AUTH_TOKEN = secrets.token_urlsafe(32)
        try:
            token_file.write_text(AUTH_TOKEN, encoding="utf-8")
        except Exception:
            pass

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)
