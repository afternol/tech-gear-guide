-- ============================================================
-- Tech Gear Guide Supabase スキーマ
-- 対象: Supabase Dashboard > SQL Editor で実行
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- Phase 1: コアテーブル
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS articles (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title                 TEXT        NOT NULL,
    slug                  TEXT        NOT NULL UNIQUE,
    body                  TEXT        NOT NULL,
    category              TEXT        NOT NULL
                              CHECK (category IN ('smartphone','tablet','windows','cpu_gpu','ai','xr','wearable','general')),
    tags                  TEXT[]      NOT NULL DEFAULT '{}',
    article_type          TEXT        NOT NULL
                              CHECK (article_type IN ('A型速報','B型深掘り','C型リーク')),
    source_reliability    INT         NOT NULL DEFAULT 0
                              CHECK (source_reliability BETWEEN 0 AND 5),
    sources               JSONB       NOT NULL DEFAULT '[]',   -- [{title, url, media}]
    featured_image_url    TEXT        NOT NULL DEFAULT '',
    featured_image_source TEXT        NOT NULL DEFAULT '',     -- press / unsplash / fallback
    featured_image_credit TEXT        NOT NULL DEFAULT '',
    seo_description       TEXT        NOT NULL DEFAULT '',
    published_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_major_update_at  TIMESTAMPTZ,                         -- Progressive大型更新時に更新
    progressive_phase     INT         CHECK (progressive_phase BETWEEN 1 AND 3),
    is_published          BOOL        NOT NULL DEFAULT TRUE,
    is_must_catch         BOOL        NOT NULL DEFAULT FALSE,
    is_leak               BOOL        NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE  articles                       IS 'Tech Gear Guide 記事テーブル';
COMMENT ON COLUMN articles.sources               IS '[{title: string, url: string, media: string}]';
COMMENT ON COLUMN articles.progressive_phase     IS '1=速報 / 2=詳細 / 3=決定版 / NULL=通常記事';
COMMENT ON COLUMN articles.last_major_update_at  IS 'Progressive記事で文字数が前版の1.5倍以上になった更新日時';


-- ────────────────────────────────────────────────────────────
-- Phase 1: インデックス
-- ────────────────────────────────────────────────────────────

-- 記事一覧ページ用（カテゴリ × 降順）
CREATE INDEX IF NOT EXISTS idx_articles_category_published
    ON articles(category, published_at DESC);

-- トップページ用（公開済み × 降順）
CREATE INDEX IF NOT EXISTS idx_articles_published_at
    ON articles(published_at DESC)
    WHERE is_published = TRUE;

-- MUST_CATCH速報のフィルタリング
CREATE INDEX IF NOT EXISTS idx_articles_must_catch
    ON articles(published_at DESC)
    WHERE is_must_catch = TRUE AND is_published = TRUE;

-- Progressive更新対象の抽出
CREATE INDEX IF NOT EXISTS idx_articles_progressive
    ON articles(progressive_phase, last_major_update_at DESC)
    WHERE progressive_phase IS NOT NULL;

-- タグ検索（GIN）
CREATE INDEX IF NOT EXISTS idx_articles_tags
    ON articles USING GIN(tags);


-- ────────────────────────────────────────────────────────────
-- Phase 1: RLS（Row Level Security）
-- ────────────────────────────────────────────────────────────

ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

-- フロントエンド（anon key）: 公開記事の読み取りのみ
CREATE POLICY "anon_read_published" ON articles
    FOR SELECT
    TO anon
    USING (is_published = TRUE);

-- パイプライン（service_role key）: 全操作
-- service_role は RLS をバイパスするため追加ポリシー不要


-- ────────────────────────────────────────────────────────────
-- Phase 2: PVトラッキングテーブル（3ヶ月目以降に追加）
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS page_views (
    id          BIGSERIAL   PRIMARY KEY,
    article_id  UUID        REFERENCES articles(id) ON DELETE CASCADE,
    slug        TEXT        NOT NULL,
    viewed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    referrer    TEXT        DEFAULT ''  -- 'discovery' / 'organic' / 'direct' / 'social'
);

CREATE INDEX IF NOT EXISTS idx_page_views_slug       ON page_views(slug);
CREATE INDEX IF NOT EXISTS idx_page_views_viewed_at  ON page_views(viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_page_views_article_id ON page_views(article_id);

ALTER TABLE page_views ENABLE ROW LEVEL SECURITY;

-- フロントエンドからのINSERT（閲覧カウント送信）を許可
CREATE POLICY "anon_insert_page_views" ON page_views
    FOR INSERT TO anon WITH CHECK (TRUE);

-- 読み取りはservice_roleのみ
CREATE POLICY "service_read_page_views" ON page_views
    FOR SELECT TO service_role USING (TRUE);


-- ────────────────────────────────────────────────────────────
-- Phase 2: 流入減衰検知ビュー（週次リフレッシュバッチ用）
-- ────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW article_decay_report AS
SELECT
    a.slug,
    a.title,
    a.category,
    a.published_at,
    COALESCE(SUM(CASE WHEN pv.viewed_at >= NOW() - INTERVAL '7 days'  THEN 1 ELSE 0 END), 0) AS views_this_week,
    COALESCE(SUM(CASE WHEN pv.viewed_at >= NOW() - INTERVAL '14 days'
                       AND pv.viewed_at <  NOW() - INTERVAL '7 days'  THEN 1 ELSE 0 END), 0) AS views_last_week,
    CASE
        WHEN COALESCE(SUM(CASE WHEN pv.viewed_at >= NOW() - INTERVAL '14 days'
                               AND pv.viewed_at <  NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END), 0) = 0
        THEN NULL
        ELSE ROUND(
            COALESCE(SUM(CASE WHEN pv.viewed_at >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END), 0)::NUMERIC
            / COALESCE(SUM(CASE WHEN pv.viewed_at >= NOW() - INTERVAL '14 days'
                               AND pv.viewed_at <  NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END), 0)::NUMERIC
            * 100, 1
        )
    END AS wow_ratio   -- 前週比(%)。50以下がリフレッシュ対象
FROM articles a
LEFT JOIN page_views pv ON a.slug = pv.slug
WHERE a.is_published = TRUE
  AND a.published_at >= NOW() - INTERVAL '90 days'  -- 3ヶ月以内の記事のみ対象
GROUP BY a.slug, a.title, a.category, a.published_at;

COMMENT ON VIEW article_decay_report IS '前週比50%以下の記事をリフレッシュキューに投入するために使用';


-- ────────────────────────────────────────────────────────────
-- Phase 3: スペックDBテーブル（6ヶ月目以降）
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS device_specs (
    id            UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    device_name   TEXT    NOT NULL,
    manufacturer  TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    release_year  INT,
    specs         JSONB   NOT NULL DEFAULT '{}',  -- {cpu, ram, storage, battery, display, camera...}
    price_usd     INT,
    price_jpy     INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_device_specs_name
    ON device_specs(manufacturer, device_name);

CREATE INDEX IF NOT EXISTS idx_device_specs_category
    ON device_specs(category, release_year DESC);

COMMENT ON TABLE  device_specs       IS 'デバイススペックDB。比較ページ・アフィリエイト最適化に使用';
COMMENT ON COLUMN device_specs.specs IS '{cpu: string, ram_gb: int, storage_gb: int, battery_mah: int, display_inch: float, ...}';


-- ────────────────────────────────────────────────────────────
-- Phase 3: 価格追跡テーブル
-- ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS price_history (
    id          BIGSERIAL   PRIMARY KEY,
    device_id   UUID        REFERENCES device_specs(id) ON DELETE CASCADE,
    price_jpy   INT         NOT NULL,
    source      TEXT        NOT NULL,  -- 'amazon' / 'apple_store' / 'rakuten' 等
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_history_device
    ON price_history(device_id, recorded_at DESC);

COMMENT ON TABLE price_history IS '価格推移。「今が買い時か」判定記事・アフィリエイト最適化に使用';


-- ────────────────────────────────────────────────────────────
-- ユーティリティ関数
-- ────────────────────────────────────────────────────────────

-- 記事数をカテゴリ別に集計（ダッシュボード用）
CREATE OR REPLACE FUNCTION get_category_stats()
RETURNS TABLE(category TEXT, total BIGINT, last_7d BIGINT, last_24h BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT
        category,
        COUNT(*)                                                              AS total,
        COUNT(*) FILTER (WHERE published_at >= NOW() - INTERVAL '7 days')   AS last_7d,
        COUNT(*) FILTER (WHERE published_at >= NOW() - INTERVAL '24 hours') AS last_24h
    FROM articles
    WHERE is_published = TRUE
    GROUP BY category
    ORDER BY total DESC;
$$;

-- リフレッシュ対象記事の取得（週次バッチが呼ぶ）
CREATE OR REPLACE FUNCTION get_refresh_candidates(wow_threshold INT DEFAULT 50)
RETURNS TABLE(slug TEXT, title TEXT, category TEXT, wow_ratio NUMERIC)
LANGUAGE sql STABLE AS $$
    SELECT slug, title, category, wow_ratio
    FROM article_decay_report
    WHERE wow_ratio <= wow_threshold
    ORDER BY wow_ratio ASC
    LIMIT 20;
$$;


-- ────────────────────────────────────────────────────────────
-- Storage バケット（SQL Editor では設定不可・Dashboardで手動作成）
-- ────────────────────────────────────────────────────────────

-- Supabase Dashboard > Storage で以下を作成:
--
-- バケット名: article-images
-- Public:    true（公開アクセス可）
-- ファイルサイズ制限: 5MB
-- 許可MIMEタイプ: image/jpeg, image/webp, image/png
--
-- フォルダ構成:
--   article-images/thumbnails/{slug}.jpg   ← アイキャッチ画像


-- ────────────────────────────────────────────────────────────
-- 初期確認クエリ（スキーマ作成後に実行して動作確認）
-- ────────────────────────────────────────────────────────────

-- SELECT get_category_stats();
-- SELECT slug, title FROM articles LIMIT 5;
-- SELECT * FROM article_decay_report LIMIT 10;
