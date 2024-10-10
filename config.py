import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Ottieni il token dal file .env
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SCRAPER_API_URL = os.getenv("SCRAPER_API_URL", "http://localhost:8000")
API_KEY = os.getenv("SCRAPER_API_KEY")