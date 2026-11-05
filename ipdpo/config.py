"""IPDPO configuration module."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if it exists
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

DEFAULT_DB_PATH = Path(os.getenv("IPDPO_DB_PATH", "ipdpo.db"))
if not DEFAULT_DB_PATH.is_absolute():
    DEFAULT_DB_PATH = PROJECT_ROOT / DEFAULT_DB_PATH

DEFAULT_EXPORT_DIR = Path(os.getenv("IPDPO_DEFAULT_EXPORT_DIR", "exports"))
if not DEFAULT_EXPORT_DIR.is_absolute():
    DEFAULT_EXPORT_DIR = PROJECT_ROOT / DEFAULT_EXPORT_DIR

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

ACTIVE_PROJECT_FILE = PROJECT_ROOT / ".active_project"
