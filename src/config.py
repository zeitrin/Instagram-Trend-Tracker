# ===== Настройки прототипа =====
import os
from pathlib import Path

# корень проекта (папка, где лежит main.py)
ROOT = Path(__file__).resolve().parent.parent

# токен берется из переменной окружения APIFY_TOKEN
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

ACCOUNTS = [
    # вставить интересующие аккаунты.
]

POSTS_PER_ACCOUNT = 40

# База в Docker (порт 5433)
DB_DSN = "dbname=trends user=postgres password=postgres host=127.0.0.1 port=5433"

# Прокси для скачивания картинок с CDN Instagram (Happ / Xray). None - напрямую.
PROXY = "socks5h://127.0.0.1:10808"

# Локальная vision-модель в Ollama
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5vl:7b"   # слабая видеокарта (<8 ГБ) -> "qwen2.5vl:3b"

# Пост считается выбросом, если вовлеченность >= LIFT_THRESHOLD x медиана аккаунта
LIFT_THRESHOLD = 2.0
MAX_OUTLIERS = 100      # сколько выбросов максимум разбирать моделью за запуск

# Выбросы и тренды ищутся только среди постов не старше MAX_POST_AGE_DAYS дней.
# Более старые посты всё равно собираются и используются как "норма" аккаунта (медиана).
# None - без ограничения.
MAX_POST_AGE_DAYS = 14

# Внутри этого окна: "сейчас" = последние RECENT_DAYS дней, остальное - "раньше".
# Должно быть меньше MAX_POST_AGE_DAYS, иначе сравнивать будет не с чем.
RECENT_DAYS = 7


def min_post_ts():
    """Unix-время самого старого поста, который ещё учитывается (0 - без ограничения)."""
    import time
    if not MAX_POST_AGE_DAYS:
        return 0
    return int(time.time()) - MAX_POST_AGE_DAYS * 86400

IMAGES_DIR = ROOT / "images"
REPORT_FILE = ROOT / "report.html"
