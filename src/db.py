import psycopg2

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  shortcode    text PRIMARY KEY,
  account      text,
  ts           bigint,
  likes        int,
  comments     int,
  views        int,
  type         text,
  caption      text,
  image_url    text,
  image_path   text,
  collected_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tags (
  shortcode  text PRIMARY KEY REFERENCES posts(shortcode) ON DELETE CASCADE,
  lift       double precision,
  is_tshirt  boolean,
  print_text text,
  theme      text,
  style      text,
  motifs     text[],
  summary    text,
  model      text,
  created_at timestamptz DEFAULT now()
);
"""


# Оценка каждого поста относительно нормы его аккаунта.
# - скрытые лайки хранятся как NULL и не участвуют в медиане;
# - lift_eng: (лайки + 3 x комментарии) / медиана аккаунта;
#   если лайки скрыты - по комментариям: (комм. + 1) / (медиана комм. + 1);
# - lift_views: просмотры / медиана просмотров видео этого аккаунта;
# - lift = лучший из двух, basis - по какому показателю он получен.
SCORED_SQL = """
WITH base AS (
  SELECT p.*,
         CASE WHEN p.likes IS NOT NULL THEN p.likes + 3 * COALESCE(p.comments, 0) END AS eng,
         CASE WHEN COALESCE(p.views, 0) > 0 THEN p.views END AS video_views
  FROM posts p
),
norms AS (
  SELECT account,
         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY eng)                    AS med_eng,
         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY likes)                  AS med_likes,
         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY COALESCE(comments, 0))  AS med_comments,
         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY video_views)            AS med_views
  FROM base GROUP BY account
),
lifts AS (
  SELECT b.*, n.med_eng, n.med_likes, n.med_comments, n.med_views,
         CASE WHEN b.eng IS NOT NULL THEN b.eng / NULLIF(n.med_eng, 0)
              ELSE (COALESCE(b.comments, 0) + 1) / (COALESCE(n.med_comments, 0) + 1)
         END AS lift_eng,
         b.video_views / NULLIF(n.med_views, 0) AS lift_views
  FROM base b JOIN norms n USING (account)
)
SELECT *,
       GREATEST(lift_eng, lift_views) AS lift,
       CASE WHEN lift_views IS NOT NULL AND lift_views >= COALESCE(lift_eng, 0) THEN 'views'
            WHEN likes IS NULL THEN 'comments'
            ELSE 'likes'
       END AS basis
FROM lifts
"""

# Условие "пост - выброс" (используется в analyze и report). Параметры - outlier_params().
OUTLIER_WHERE = """
  s.lift >= %(lift)s
  AND s.ts >= %(since)s
  AND (s.likes >= %(min_likes)s
       OR s.views >= %(min_views)s
       OR (s.likes IS NULL AND s.comments >= %(min_comments)s))
"""


def outlier_params(**extra):
    params = {
        "lift": config.LIFT_THRESHOLD,
        "since": config.min_post_ts(),
        "min_likes": config.MIN_LIKES,
        "min_views": config.MIN_VIEWS,
        "min_comments": config.MIN_COMMENTS,
    }
    params.update(extra)
    return params


def get_conn():
    conn = psycopg2.connect(config.DB_DSN)
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
    return conn
