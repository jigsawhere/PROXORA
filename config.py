import os

# config.py
# For local development, you can keep your keys here.
# For deployment, these should be set as environment variables on the hosting platform.
# The os.getenv() function will first look for an environment variable.
# If it's not found (e.g., when running locally without setting them), it will use the hardcoded value.

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8171951306:AAHKMLXhRmZ7HIPRcZ8JqkKGJmScBIYhen0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAZBUnaZPajabGE_u7gFtXgCJ2V8Irh0BU")
TTSOPENAI_API_KEY = os.getenv("TTSOPENAI_API_KEY", "tts-e563182efb6a109f220e02f5e3483192") # IMPORTANT: Replace with your actual Play.ht key for local testing
