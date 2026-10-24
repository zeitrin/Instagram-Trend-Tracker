# ===== Настройки прототипа =====
import os
from pathlib import Path

# корень проекта (папка, где лежит main.py)
ROOT = Path(__file__).resolve().parent.parent

# токен берется из переменной окружения APIFY_TOKEN
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

ACCOUNTS = [
    "vrode_rovno.tm",
    "evch_0",
    "phoenician_rus",
    "miniline_shop",
    "futbolkiruss.ru",
    "moar_clo",
    "aizi__store",
]

POSTS_PER_ACCOUNT = 40

# База в Docker (порт 5433)
DB_DSN = "dbname=trends user=postgres password=postgres host=127.0.0.1 port=5433"

# Прокси для скачивания картинок с CDN Instagram (Happ / Xray). None - напрямую.
PROXY = "socks5h://127.0.0.1:10808"

# Локальная vision-модель в Ollama
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5vl:7b"   # слабая видеокарта (<8 ГБ) -> "qwen2.5vl:3b"

# Пост считается выбросом, если он набрал >= LIFT_THRESHOLD x норму своего аккаунта.
# Норма считается отдельно по лайкам (+3 x комментарии) и по просмотрам видео,
# берется лучший из двух показателей.
LIFT_THRESHOLD = 2.0

# Минимальный абсолютный уровень, чтобы пост вообще мог стать выбросом
# (отсекает "x3" у постов с 30 лайками). Достаточно выполнить одно из условий.
MIN_LIKES = 50          # лайков
MIN_VIEWS = 1000        # просмотров (для видео / Reels)
MIN_COMMENTS = 5        # комментариев (для постов со скрытыми лайками)
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
