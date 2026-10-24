import os
from datetime import datetime

import requests
from apify_client import ApifyClient

import config
from db import get_conn


def to_unix(ts):
    if not ts:
        return None
    if isinstance(ts, (int, float)):
        return int(ts)
    return int(datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp())


def as_dict(item):
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(by_alias=True)
    return dict(item)


def dataset_id_of(run):
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    return getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId")


def collect():
    client = ApifyClient(config.APIFY_TOKEN)
    print(f"Сбор: {len(config.ACCOUNTS)} аккаунтов x {config.POSTS_PER_ACCOUNT} постов (несколько минут)...")
    run = client.actor("apify/instagram-scraper").call(run_input={
        "directUrls": [f"https://www.instagram.com/{a}/" for a in config.ACCOUNTS],
        "resultsType": "posts",
        "resultsLimit": config.POSTS_PER_ACCOUNT,
    })
    items = [as_dict(i) for i in client.dataset(dataset_id_of(run)).iterate_items()]
    print("получено элементов:", len(items))
    return items


def save(conn, items):
    saved = 0
    with conn.cursor() as cur:
        for p in items:
            if p.get("error") or not p.get("shortCode"):
                if p.get("error"):
                    print("ошибка Apify:", p.get("url") or p.get("inputUrl"), p.get("error"))
                continue
            cur.execute(
                """
                INSERT INTO posts (shortcode, account, ts, likes, comments, views, type, caption, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (shortcode) DO UPDATE SET
                  likes = EXCLUDED.likes,
                  comments = EXCLUDED.comments,
                  views = EXCLUDED.views,
                  image_url = EXCLUDED.image_url,
                  collected_at = now()
                """,
                (
                    p.get("shortCode"),
                    p.get("ownerUsername"),
                    to_unix(p.get("timestamp")),
                    max(p.get("likesCount") or 0, 0),
                    max(p.get("commentsCount") or 0, 0),
                    p.get("videoPlayCount") or p.get("videoViewCount") or 0,
                    p.get("type"),
                    p.get("caption") or "",
                    p.get("displayUrl"),
                ),
            )
            saved += 1
    conn.commit()
    print("сохранено постов:", saved)


def download_images(conn):
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    s = requests.Session()
    if config.PROXY:
        s.proxies = {"http": config.PROXY, "https": config.PROXY}
    s.headers["User-Agent"] = "Mozilla/5.0"

    with conn.cursor() as cur:
        cur.execute("SELECT shortcode, image_url FROM posts WHERE image_path IS NULL AND image_url IS NOT NULL")
        rows = cur.fetchall()

    print(f"Скачиваю картинки: {len(rows)}")
    ok = 0
    for shortcode, url in rows:
        path = os.path.join(config.IMAGES_DIR, f"{shortcode}.jpg")
        try:
            if not os.path.exists(path):
                r = s.get(url, timeout=30)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
            with conn.cursor() as cur:
                cur.execute("UPDATE posts SET image_path = %s WHERE shortcode = %s", (path, shortcode))
            ok += 1
        except Exception as ex:
            print("не скачалось", shortcode, ex)
    conn.commit()
    print("скачано:", ok)


if __name__ == "__main__":
    conn = get_conn()
    save(conn, collect())
    download_images(conn)
    print("Готово. Дальше: python analyze.py")
