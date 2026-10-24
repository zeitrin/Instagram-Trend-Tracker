import psycopg2
import config

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


def get_conn():
    conn = psycopg2.connect(config.DB_DSN)
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
    return conn
