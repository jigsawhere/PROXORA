# config.py

import os
from dotenv import load_dotenv

# This line loads the variables from a .env file if it exists
# (useful for local development)
load_dotenv()

# Read the secret keys from the environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PLAYHT_API_KEY = os.environ.get("PLAYHT_API_KEY")

# You might also need the Play.ht User ID, which should also be an environment variable
PLAYHT_USER_ID = os.environ.get("PLAYHT_USER_ID")


# --- Verification (Optional but Recommended) ---
# This code checks if the variables were loaded correctly when the app starts.
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    raise ValueError("Missing required environment variable: GEMINI_API_KEY")
if not PLAYHT_API_KEY:
    raise ValueError("Missing required environment variable: PLAYHT_API_KEY")
