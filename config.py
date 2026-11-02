"""
App-wide settings, loaded once at startup.

- Accepts either GEMINI_API_KEY or GOOGLE_API_KEY and exposes both,
  because the Gemini SDK, LangChain and CrewAI each read a different name.
- Currency formatting for prompts and reports (defaults to Indian rupees).
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if _api_key:
    os.environ.setdefault("GEMINI_API_KEY", _api_key)
    os.environ.setdefault("GOOGLE_API_KEY", _api_key)

CURRENCY = os.getenv("CURRENCY_SYMBOL", "₹")

# Where per-user vector stores and upload stats are kept
DATA_DIR = os.getenv("DATA_DIR", "./chroma_db")

# Comma-separated list of allowed frontend origins; "*" allows any
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def money(amount) -> str:
    """Format an amount for prompts and reports, e.g. ₹85,000.00"""
    return f"{CURRENCY}{float(amount or 0):,.2f}"
