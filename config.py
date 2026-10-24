import os

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

ACCOUNTS = [
    "threadless",
    "redbubble",
    "designbyhumans",
    "ripndip",
    "stussy",
    "obeyclothing",
    "supremenewyork",
    "palaceskateboards",
    "wearebraindead",
    "onlineceramics",
    "hufworldwide",
    "antisocialsocialclub",
    "sp5derworldwide",
    "trapstarlondon",
    "kith",
]

POSTS_PER_ACCOUNT = 40

# База в Docker (порт 5433)
DB_DSN = "dbname=trends user=postgres password=postgres host=127.0.0.1 port=5433"

# Прокси для скачивания картинок с CDN Instagram (Happ / Xray). None - напрямую.
PROXY = "socks5h://127.0.0.1:10808"

# Локальная vision-модель в Ollama
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5vl:7b"

# Пост считается выбросом, если вовлеченность >= LIFT_THRESHOLD x медиана аккаунта
LIFT_THRESHOLD = 2.0
MAX_OUTLIERS = 100      # сколько выбросов максимум разбирать моделью за запуск

# "Сейчас" = последние RECENT_DAYS дней, всё что раньше - "раньше"
RECENT_DAYS = 28

IMAGES_DIR = "images"
REPORT_FILE = "report.html"
