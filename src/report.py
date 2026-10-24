"""Шаг 3. Расчет трендов и HTML-отчет."""
import base64
import html
import io
import os
import webbrowser
from collections import defaultdict
from datetime import datetime, timezone

from PIL import Image

from . import config
from .db import OUTLIER_WHERE, SCORED_SQL, get_conn, outlier_params

THEME_RU = {
    "logo/brand": "Логотип / бренд", "text/slogan": "Текст / слоган", "meme/humor": "Мемы / юмор",
    "anime/manga": "Аниме / манга", "cartoon/character": "Мультяшные персонажи", "animals": "Животные",
    "skull/gothic": "Черепа / готика", "religious/angel": "Религия / ангелы", "cars/racing": "Авто / гонки",
    "sports/varsity": "Спорт / колледж", "music/band": "Музыка / группы", "nature/landscape": "Природа",
    "space/sci-fi": "Космос / sci-fi", "psychedelic": "Психоделика", "food": "Еда",
    "pop culture/movie": "Поп-культура / кино", "abstract/pattern": "Абстракция / паттерн", "other": "Другое",
}
STYLE_RU = {
    "vintage/distressed": "Винтаж / потертость", "minimalist": "Минимализм", "y2k/chrome": "Y2K / хром",
    "grunge": "Гранж", "hand-drawn/illustration": "Ручная иллюстрация", "photo print": "Фотопринт",
    "puff/3d print": "Объемный (puff) принт", "graffiti": "Граффити", "retro 70s/80s": "Ретро 70-80-х",
    "cartoon/flat": "Мульт / флэт", "bold typography": "Крупная типографика", "other": "Другое",
}


# ---------- расчет ----------

def load(conn):
    with conn.cursor() as cur:
        since = config.min_post_ts()
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT account), MIN(ts), MAX(ts) FROM posts WHERE ts >= %s", (since,))
        n_posts, n_accounts, min_ts, max_ts = cur.fetchone()
        # lift пересчитывается здесь, а не берется из tags: так отчет всегда
        # соответствует текущим настройкам и свежим лайкам/просмотрам.
        cur.execute(
            f"""
            WITH scored AS ({SCORED_SQL})
            SELECT s.shortcode, s.account, s.ts, s.likes, s.comments, s.views, s.image_path,
                   s.lift, s.basis, s.med_likes, s.med_comments, s.med_views,
                   t.is_tshirt, t.print_text, t.theme, t.style, t.motifs, t.summary
            FROM scored s JOIN tags t USING (shortcode)
            WHERE {OUTLIER_WHERE}
            ORDER BY s.lift DESC
            """,
            outlier_params(),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    stats = {"posts": n_posts, "accounts": n_accounts, "min_ts": min_ts, "max_ts": max_ts}
    return stats, rows


def compute_trends(rows, key, max_ts, recent_days, min_count=2, min_accounts=2):
    """Сравнивает долю признака среди выбросов 'сейчас' и 'раньше'.
    Доли (а не абсолютные числа) - чтобы не зависеть от того, как часто постят аккаунты."""
    cutoff = max_ts - recent_days * 86400
    recent = [r for r in rows if r["ts"] and r["ts"] >= cutoff]
    older = [r for r in rows if r["ts"] and r["ts"] < cutoff]

    def values(r):
        v = r.get(key)
        if isinstance(v, (list, tuple)):
            return set(v)
        return {v} if v else set()

    groups = defaultdict(lambda: {"recent": [], "older": []})
    for r in recent:
        for v in values(r):
            groups[v]["recent"].append(r)
    for r in older:
        for v in values(r):
            groups[v]["older"].append(r)

    n_rec, n_old = len(recent), len(older)
    out = []
    for v, g in groups.items():
        rc, oc = len(g["recent"]), len(g["older"])
        share_rec = (rc + 0.5) / (n_rec + 1)
        share_old = (oc + 0.5) / (n_old + 1)
        accounts = {r["account"] for r in g["recent"]}
        out.append({
            "value": v,
            "recent": rc,
            "older": oc,
            "share_recent": rc / n_rec if n_rec else 0,
            "share_older": oc / n_old if n_old else 0,
            "growth": share_rec / share_old if n_old else None,
            "accounts": len(accounts),
            "examples": sorted(g["recent"], key=lambda r: -(r["lift"] or 0))[:4],
            "rising": rc >= min_count and len(accounts) >= min_accounts and n_old > 0 and share_rec > share_old * 1.2,
        })
    out.sort(key=lambda x: (x["rising"], x["growth"] or 0, x["recent"]), reverse=True)
    return out, n_rec, n_old


# ---------- HTML ----------

_thumb_cache = {}


def thumb(path, size=360):
    if not path or not os.path.exists(path):
        return ""
    if path not in _thumb_cache:
        img = Image.open(path).convert("RGB")
        img.thumbnail((size, size))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=78)
        _thumb_cache[path] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return _thumb_cache[path]


def link(r):
    return f"https://www.instagram.com/p/{r['shortcode']}/"


def esc(s):
    return html.escape(str(s or ""))


def date(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d.%m.%Y") if ts else "-"


def num(n):
    """1234 -> 1.2K, 2500000 -> 2.5M"""
    if n is None:
        return "?"
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.0f}K"
    if n >= 1000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return f"{n:.0f}"


BASIS_RU = {"likes": "по лайкам", "views": "по просмотрам", "comments": "по комментариям"}


def metrics_line(r):
    likes = "скрыты" if r["likes"] is None else num(r["likes"])
    parts = [f"{likes} ♥", f"{num(r['comments'] or 0)} 💬"]
    if r.get("views"):
        parts.append(f"{num(r['views'])} ▶")
    return " · ".join(parts)


def norm_line(r):
    if r["basis"] == "views":
        norm = f"{num(r['med_views'])} ▶"
    elif r["basis"] == "comments":
        norm = f"{num(r['med_comments'])} 💬"
    else:
        norm = f"{num(r['med_likes'])} ♥"
    return f"{BASIS_RU.get(r['basis'], '')}, норма аккаунта {norm}"


def mini_gallery(examples):
    return "".join(
        f'<a href="{link(r)}" target="_blank" title="@{esc(r["account"])} x{r["lift"]:.1f}">'
        f'<img src="{thumb(r["image_path"], 200)}" loading="lazy"></a>'
        for r in examples if r.get("image_path")
    )


def growth_badge(t):
    if t["growth"] is None:
        return '<span class="badge">новое</span>'
    cls = "up" if t["rising"] else ("down" if t["growth"] < 0.9 else "flat")
    return f'<span class="badge {cls}">x{t["growth"]:.1f}</span>'


def trend_cards(trends, labels=None, limit=8):
    rising = [t for t in trends if t["rising"]][:limit]
    if not rising:
        return '<p class="muted">Явно растущих не найдено - попробуйте больше аккаунтов или постов.</p>'
    cards = []
    for t in rising:
        name = labels.get(t["value"], t["value"]) if labels else t["value"]
        cards.append(f"""
        <div class="card">
          <div class="card-head"><h3>{esc(name)}</h3>{growth_badge(t)}</div>
          <div class="meta">{t["recent"]} выбросов сейчас · {t["older"]} раньше · {t["accounts"]} аккаунтов</div>
          <div class="mini">{mini_gallery(t["examples"])}</div>
        </div>""")
    return '<div class="cards">' + "".join(cards) + "</div>"


def share_table(trends, labels):
    rows = []
    for t in sorted(trends, key=lambda x: -x["share_recent"]):
        if t["recent"] == 0 and t["older"] == 0:
            continue
        name = labels.get(t["value"], t["value"])
        rows.append(f"""
        <tr>
          <td>{esc(name)}</td>
          <td><div class="bar"><span style="width:{t['share_recent']*100:.0f}%"></span></div>{t['share_recent']*100:.0f}%</td>
          <td class="muted">{t['share_older']*100:.0f}%</td>
          <td>{growth_badge(t)}</td>
          <td class="muted">{t['accounts']}</td>
        </tr>""")
    return f"""
    <table>
      <thead><tr><th></th><th>Сейчас</th><th>Раньше</th><th>Динамика</th><th>Аккаунтов</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def build_html(stats, tees, all_tagged, themes, styles, motifs, n_rec, n_old):
    cutoff = stats["max_ts"] - config.RECENT_DAYS * 86400
    texts = [r for r in tees if r["print_text"] and r["ts"] >= cutoff][:30]
    top = tees[:24]

    texts_html = "".join(
        f'<li><a href="{link(r)}" target="_blank">«{esc(r["print_text"])}»</a>'
        f' <span class="muted">@{esc(r["account"])} · x{r["lift"]:.1f}</span></li>'
        for r in texts
    ) or '<li class="muted">Надписей не найдено</li>'

    top_html = "".join(f"""
      <a class="post" href="{link(r)}" target="_blank">
        <img src="{thumb(r['image_path'])}" loading="lazy">
        <div class="post-info">
          <b>@{esc(r['account'])}</b> <span class="badge up">x{r['lift']:.1f}</span><br>
          <span class="muted">{esc(THEME_RU.get(r['theme'], r['theme']))} · {esc(STYLE_RU.get(r['style'], r['style']))}</span><br>
          <span>{metrics_line(r)}</span><br>
          <span class="muted">{norm_line(r)}</span><br>
          <span class="muted">{date(r['ts'])}</span>
        </div>
      </a>""" for r in top)

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Тренды футболок</title>
<style>
  :root {{ --bg:#0f1115; --card:#181b22; --text:#e8eaf0; --muted:#8a90a0; --accent:#ff5c39; --up:#2ecc71; --down:#e74c3c; --line:#262a33; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:32px 16px 64px; }}
  h1 {{ font-size:32px; margin:0 0 4px; }} h2 {{ margin:48px 0 8px; font-size:22px; }}
  h3 {{ margin:0; font-size:17px; }}
  .muted {{ color:var(--muted); }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-top:24px; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }}
  .stat b {{ display:block; font-size:28px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:14px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
  .meta {{ color:var(--muted); font-size:13px; margin:4px 0 10px; }}
  .mini {{ display:grid; grid-template-columns:repeat(4,1fr); gap:6px; }}
  .mini img {{ width:100%; aspect-ratio:1; object-fit:cover; border-radius:6px; display:block; }}
  .badge {{ font-size:12px; font-weight:600; padding:2px 8px; border-radius:999px; background:#2a2f3a; white-space:nowrap; }}
  .badge.up {{ background:rgba(46,204,113,.15); color:var(--up); }}
  .badge.down {{ background:rgba(231,76,60,.15); color:var(--down); }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border-radius:12px; overflow:hidden; }}
  th, td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); font-size:14px; }}
  th {{ color:var(--muted); font-weight:500; }}
  .bar {{ display:inline-block; width:90px; height:8px; background:#2a2f3a; border-radius:4px; margin-right:8px; vertical-align:middle; }}
  .bar span {{ display:block; height:100%; background:var(--accent); border-radius:4px; }}
  .two {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  @media (max-width:800px) {{ .two {{ grid-template-columns:1fr; }} }}
  ul.texts {{ columns:2; padding-left:18px; }} @media (max-width:700px) {{ ul.texts {{ columns:1; }} }}
  ul.texts li {{ margin-bottom:6px; break-inside:avoid; }}
  a {{ color:var(--text); }}
  .gallery {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; }}
  .post {{ background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; text-decoration:none; }}
  .post img {{ width:100%; aspect-ratio:1; object-fit:cover; display:block; }}
  .post-info {{ padding:10px; font-size:13px; }}
</style></head>
<body><div class="wrap">
  <h1>Тренды графических футболок</h1>
  <div class="muted">Instagram · {date(stats['min_ts'])} – {date(stats['max_ts'])} ·
  посты за последние {config.MAX_POST_AGE_DAYS or '∞'} дней · «сейчас» = последние {config.RECENT_DAYS} дней · выброс = от x{config.LIFT_THRESHOLD:g} нормы аккаунта по лайкам или просмотрам,
  минимум {config.MIN_LIKES} ♥ или {num(config.MIN_VIEWS)} ▶</div>

  <div class="stats">
    <div class="stat"><b>{stats['accounts']}</b><span class="muted">аккаунтов</span></div>
    <div class="stat"><b>{stats['posts']}</b><span class="muted">постов собрано</span></div>
    <div class="stat"><b>{len(all_tagged)}</b><span class="muted">выбросов разобрано</span></div>
    <div class="stat"><b>{len(tees)}</b><span class="muted">из них с футболками</span></div>
    <div class="stat"><b>{n_rec} / {n_old}</b><span class="muted">выбросов сейчас / раньше</span></div>
  </div>

  <h2>🔥 Растущие мотивы</h2>
  <p class="muted">Конкретные элементы принтов, чья доля среди «выстреливших» постов выросла и встречается у нескольких брендов.</p>
  {trend_cards(motifs)}

  <h2>Растущие темы</h2>
  {trend_cards(themes, THEME_RU, limit=6)}

  <h2>Темы и стили: доля среди выбросов</h2>
  <div class="two">
    <div>{share_table(themes, THEME_RU)}</div>
    <div>{share_table(styles, STYLE_RU)}</div>
  </div>

  <h2>Надписи с принтов, которые заходят сейчас</h2>
  <ul class="texts">{texts_html}</ul>

  <h2>Топ постов-выбросов</h2>
  <div class="gallery">{top_html}</div>
</div></body></html>"""


def run(open_browser=True):
    conn = get_conn()
    stats, rows = load(conn)
    conn.close()
    if not rows:
        print("Нет разобранных постов. Сначала: python main.py collect, затем python main.py analyze")
        return
    tees = [r for r in rows if r["is_tshirt"]]
    max_ts = stats["max_ts"]

    themes, n_rec, n_old = compute_trends(tees, "theme", max_ts, config.RECENT_DAYS)
    styles, _, _ = compute_trends(tees, "style", max_ts, config.RECENT_DAYS)
    motifs, _, _ = compute_trends(tees, "motifs", max_ts, config.RECENT_DAYS)

    if n_old == 0:
        print("Внимание: все выбросы за последние дни - сравнивать не с чем. "
              "Уменьшите RECENT_DAYS или увеличьте MAX_POST_AGE_DAYS в src/config.py.")

    with open(config.REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(build_html(stats, tees, rows, themes, styles, motifs, n_rec, n_old))
    print("Отчет:", config.REPORT_FILE)
    if open_browser:
        webbrowser.open(config.REPORT_FILE.as_uri())
