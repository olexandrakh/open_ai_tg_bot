import os
from dotenv import load_dotenv

load_dotenv()


CHATGPT_TOKEN = os.getenv("CHATGPT_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")


LANGUAGES = {
    "en": "🇬🇧 Англійська",
    "uk": "🇺🇦 Українська",
    "es": "🇪🇸 Іспанська",
    "fr": "🇫🇷 Французька",
    "de": "🇩🇪 Німецька",
    "pl": "🇵🇱 Польська",
    "it": "🇮🇹 Італійська",
}

print(CHATGPT_TOKEN)
print(BOT_TOKEN)
