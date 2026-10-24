import base64
import io
import json
import re

import requests
from PIL import Image

import config
from db import get_conn

THEMES = [
    "logo/brand", "text/slogan", "meme/humor", "anime/manga", "cartoon/character",
    "animals", "skull/gothic", "religious/angel", "cars/racing", "sports/varsity",
    "music/band", "nature/landscape", "space/sci-fi", "psychedelic", "food",
    "pop culture/movie", "abstract/pattern", "other",
]

STYLES = [
    "vintage/distressed", "minimalist", "y2k/chrome", "grunge", "hand-drawn/illustration",
    "photo print", "puff/3d print", "graffiti", "retro 70s/80s", "cartoon/flat",
    "bold typography", "other",
]

PROMPT = """You analyze an Instagram post from a clothing brand.
Look at the image. The caption is given only for context.

Return ONLY a JSON object with these keys:
- "is_tshirt": true if the image clearly shows a t-shirt / tee / longsleeve with a print or graphic, otherwise false
- "print_text": exact text printed on the t-shirt, "" if there is none
- "theme": exactly one of {themes}
- "style": exactly one of {styles}
- "motifs": list of up to 3 short lowercase english tags for the main visual elements of the print (e.g. "angel wings", "spider web", "vintage car")
- "summary": one short sentence describing the design

Caption: {caption}"""


def find_outliers(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH m AS (
              SELECT account,
                     PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY likes + 3 * comments) AS med
              FROM posts GROUP BY account
            )
            SELECT p.shortcode, p.image_path, p.caption,
                   (p.likes + 3 * p.comments) / NULLIF(m.med, 0) AS lift
            FROM posts p JOIN m USING (account)
            WHERE p.image_path IS NOT NULL
              AND (p.likes + 3 * p.comments) / NULLIF(m.med, 0) >= %s
              AND NOT EXISTS (SELECT 1 FROM tags t WHERE t.shortcode = p.shortcode)
            ORDER BY lift DESC
            LIMIT %s
            """,
            (config.LIFT_THRESHOLD, config.MAX_OUTLIERS),
        )
        return cur.fetchall()


def image_b64(path, max_side=768):
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def normalize(d):
    theme = str(d.get("theme", "other")).strip().lower()
    style = str(d.get("style", "other")).strip().lower()
    motifs = d.get("motifs") or []
    if isinstance(motifs, str):
        motifs = [motifs]
    return {
        "is_tshirt": bool(d.get("is_tshirt")),
        "print_text": str(d.get("print_text") or "").strip(),
        "theme": theme if theme in THEMES else "other",
        "style": style if style in STYLES else "other",
        "motifs": [str(x).strip().lower() for x in motifs if str(x).strip()][:3],
        "summary": str(d.get("summary") or "").strip(),
    }


def tag_image(session, path, caption):
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{
            "role": "user",
            "content": PROMPT.format(
                themes=json.dumps(THEMES), styles=json.dumps(STYLES), caption=(caption or "")[:300]
            ),
            "images": [image_b64(path)],
        }],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
    }
    r = session.post(f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=600)
    r.raise_for_status()
    return normalize(parse_json(r.json()["message"]["content"]))


def main():
    conn = get_conn()
    outliers = find_outliers(conn)
    print(f"Выбросов для разбора: {len(outliers)} (модель {config.OLLAMA_MODEL})")

    s = requests.Session()
    s.trust_env = False  # Ollama локальная - не пускаем через системный прокси VPN

    for i, (shortcode, path, caption, lift) in enumerate(outliers, 1):
        try:
            t = tag_image(s, path, caption)
        except Exception as ex:
            print(f"[{i}/{len(outliers)}] {shortcode}: ошибка {ex}")
            continue
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tags (shortcode, lift, is_tshirt, print_text, theme, style, motifs, summary, model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (shortcode) DO NOTHING
                """,
                (shortcode, lift, t["is_tshirt"], t["print_text"], t["theme"], t["style"],
                 t["motifs"], t["summary"], config.OLLAMA_MODEL),
            )
        conn.commit()
        mark = "футболка" if t["is_tshirt"] else "не футболка"
        print(f"[{i}/{len(outliers)}] {shortcode} x{lift:.1f} {mark} | {t['theme']} | {t['style']} | {t['motifs']}")

    print("Готово. Дальше: python report.py")


if __name__ == "__main__":
    main()
