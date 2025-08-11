# config.py
import logging
import os

from dotenv import load_dotenv

load_dotenv(".env", override=True)

# EDINET API configuration
EDINET_API_KEY: str = os.getenv("EDINET_API_KEY", "")

if not EDINET_API_KEY:
    raise ValueError("EDINET_API_KEY environment variable is required")

# Processing configuration
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
DELAY_SECONDS: int = int(os.getenv("DELAY_SECONDS", "5"))
DAYS_BACK: int = int(os.getenv("DAYS_BACK", "7"))

logging.info("Configuration loaded successfully")
