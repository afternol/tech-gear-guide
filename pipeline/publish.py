# -*- coding: utf-8 -*-
"""
Tech Gear Guide — publish.py
generated_articles.jsonl → Supabase INSERT/PATCH → ISR revalidate → Sitemap ping
"""

import asyncio
import json
import os
import sys
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx
from fetch_image import fetch_article_image

# ─────────────────────────────────────────────
# 設定（環境変数から読み込み）
# ─────────────────────────────────────────────

SUPABASE_URL             = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY     = os.getenv("SUPABASE_SERVICE_KEY", "")
NEXTJS_REVALIDATE_URL    = os.getenv("NEXTJS_REVALIDATE_URL", "")
NEXTJS_REVALIDATE_SECRET = os.getenv("NEXTJS_REVALIDATE_SECRET", "")
SITE_SITEMAP_URL         = os.getenv("SITE_SITEMAP_URL", "")

INPUT_PATH       = Path("generated_articles.jsonl")
LOG_PATH         = Path("published_log.jsonl")
MAX_PARALLEL     = 5
MAJOR_UPDATE_RATIO = 1.5

# ─────────────────────────────────────────────
# データ型
# ─────────────────────────────────────────────

@dataclass
class ArticleRow:
    title: str
    slug: str
    body: str
    category: str
    tags: list[str]
    article_type: str
    source_reliability: int
    sources: list[dict]
    featured_image_url: str
    featured_image_source: str
    featured_image_credit: str
    seo_description: str
    published_at: str
    is_published: bool = True
    is_must_catch: bool = False
    is_leak: bool = False
    progressive_phase: Optional[int] = None
    last_major_update_at: Optional[str] = None

# ─────────────────────────────────────────────
# Supabase ヘルパー
# ─────────────────────────────────────────────

def _headers(prefer: str = "return=minimal") -> dict:
    return {
        "apikey":        SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        prefer,
    }

def slug_exists(slug: str) -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                f"{SUPABASE_URL}/rest/v1/articles",
                headers=_headers(),
                params={"slug": f"eq.{slug}", "select": "id,body"},
            )
            data = r.json()
            if isinstance(data, list) and data:
                return True, data[0].get("body", "")
    except Exception:
        pass
    return False, ""

def insert_article(row: ArticleRow) -> tuple[bool, str]:
    payload = {
        "title":                 row.title,
        "slug":                  row.slug,
        "body":                  row.body,
        "category":              row.category,
        "tags":                  row.tags,
        "article_type":          row.article_type,
        "source_reliability":    row.source_reliability,
        "sources":               row.sources,
        "featured_image_url":    row.featured_image_url,
        "featured_image_source": row.featured_image_source,
        "featured_image_credit": row.featured_image_credit,
        "seo_description":       row.seo_description,
        "published_at":          row.published_at,
        "is_published":          row.is_published,
        "is_must_catch":         row.is_must_catch,
        "is_leak":               row.is_leak,
        "progressive_phase":     row.progressive_phase,
        "last_major_update_at":  row.last_major_update_at,
    }
    try:
        with httpx.Client(timeout=15) as c:
            r = c.post(
                f"{SUPABASE_URL}/rest/v1/articles",
                headers=_headers(),
                json=payload,
            )
            if r.status_code in (200, 201):
                return True, ""
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

def update_article(slug: str, updates: dict) -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=15) as c:
            r = c.patch(
                f"{SUPABASE_URL}/rest/v1/articles",
                headers=_headers(),
                params={"slug": f"eq.{slug}"},
                json=updates,
            )
            if r.status_code in (200, 204):
                return True, ""
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

# ─────────────────────────────────────────────
# Supabase Storage
# ─────────────────────────────────────────────

STORAGE_BUCKET = "article-images"

def upload_image(local_path: str, slug: str) -> Optional[str]:
    file_path = Path(local_path)
    if not file_path.exists():
        return None
    storage_key = f"thumbnails/{slug}.jpg"
    upload_url  = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_key}"
    public_url  = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_key}"
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                upload_url,
                headers={
                    "apikey":        SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type":  "image/jpeg",
                    "x-upsert":      "true",
                },
                content=file_path.read_bytes(),
            )
            if r.status_code in (200, 201):
                return public_url
    except Exception as e:
        print(f"  ⚠️  画像アップロードエラー: {e}")
    return None

# ─────────────────────────────────────────────
# ISR revalidate / Sitemap ping
# ─────────────────────────────────────────────

def revalidate(slug: str) -> bool:
    if not NEXTJS_REVALIDATE_URL:
        return True
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                NEXTJS_REVALIDATE_URL,
                params={"secret": NEXTJS_REVALIDATE_SECRET, "path": f"/articles/{slug}"},
            )
            return r.status_code == 200
    except Exception:
        return False

async def ping_sitemap() -> bool:
    if not SITE_SITEMAP_URL:
        return True
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://www.google.com/ping", params={"sitemap": SITE_SITEMAP_URL})
            return r.status_code == 200
    except Exception:
        return False

def is_major_update(old_body: str, new_body: str) -> bool:
    old_len = len(old_body)
    if old_len == 0:
        return True
    return len(new_body) / old_len >= MAJOR_UPDATE_RATIO

# ─────────────────────────────────────────────
# 1記事分の処理
# ─────────────────────────────────────────────

async def publish_one(article: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        slug             = article.get("slug", "")
        title            = article.get("title", "")
        progressive_phase = article.get("progressive_phase")
        is_must_catch    = article.get("is_must_catch", False)
        article_type     = article.get("article_type", "A型速報")

        log = {
            "slug":         slug,
            "title":        title[:60],
            "status":       "failed",
            "reason":       "",
            "action":       "",
            "image_src":    "",
            "sitemap_ping": False,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        exists, old_body = slug_exists(slug)

        if exists and progressive_phase is None:
            log["status"] = "skipped"
            log["action"] = "skipped"
            log["reason"] = "slug already exists"
            print(f"  ⏭️  スキップ（重複）: {slug}")
            return log

        new_body   = article.get("body", "")
        needs_ping = False
        action     = ""

        # Progressive更新（B型続報）
        if exists and progressive_phase is not None:
            major = is_major_update(old_body, new_body)
            now   = datetime.now(timezone.utc).isoformat()
            updates = {
                "body":                 new_body,
                "progressive_phase":    progressive_phase,
                "seo_description":      article.get("seo_description", ""),
                "tags":                 article.get("tags", []),
                "sources":              article.get("sources", []),
                "last_major_update_at": now if major else None,
            }
            ok, err = update_article(slug, updates)
            if not ok:
                log["reason"] = err
                print(f"  ❌ UPDATE失敗: {slug} — {err[:80]}")
                return log
            action     = "updated"
            needs_ping = major
            print(f"  🔄 Progressive更新（Phase{progressive_phase}{'・大型' if major else ''}）: {title[:50]}")

        # 新規INSERT
        else:
            img_result     = fetch_article_image(
                title=title,
                category=article.get("category", "general"),
                article_type=article_type,
                slug=slug,
                tags=article.get("tags", []),
            )
            # Storageアップロード成功 → Storage URL、失敗 → 直接URL（Unsplash/フォールバック）
            public_img_url = ""
            if img_result.get("local_path"):
                public_img_url = upload_image(img_result["local_path"], slug) or ""
            if not public_img_url:
                public_img_url = img_result.get("url", "")

            row = ArticleRow(
                title=title,
                slug=slug,
                body=new_body,
                category=article.get("category", "general"),
                tags=article.get("tags", []),
                article_type=article_type,
                source_reliability=article.get("source_reliability", 0),
                sources=article.get("sources", []),
                featured_image_url=public_img_url,
                featured_image_source=img_result.get("source", ""),
                featured_image_credit=img_result.get("credit", ""),
                seo_description=article.get("seo_description", ""),
                published_at=article.get("published_at", datetime.now(timezone.utc).isoformat()),
                is_must_catch=is_must_catch,
                is_leak=article.get("is_leak", False),
                progressive_phase=progressive_phase,
            )
            ok, err = insert_article(row)
            if not ok:
                log["reason"] = err
                print(f"  ❌ INSERT失敗: {slug} — {err[:80]}")
                return log
            action         = "inserted"
            log["image_src"] = img_result.get("source", "")
            needs_ping     = is_must_catch or "C型" in article_type
            print(f"  ✅ 公開: {title[:55]}")

        revalidate(slug)

        if needs_ping:
            pinged             = await ping_sitemap()
            log["sitemap_ping"] = pinged

        log["status"] = "published"
        log["action"] = action
        return log

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

async def main():
    if not INPUT_PATH.exists():
        print(f"入力ファイルが見つかりません: {INPUT_PATH}")
        return

    articles = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                articles.append(json.loads(line))

    print(f"投稿対象: {len(articles)} 件")
    print("=" * 60)

    sem  = asyncio.Semaphore(MAX_PARALLEL)
    logs = await asyncio.gather(*[publish_one(a, sem) for a in articles])

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for log in logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")

    inserted = sum(1 for l in logs if l.get("action") == "inserted")
    updated  = sum(1 for l in logs if l.get("action") == "updated")
    skipped  = sum(1 for l in logs if l.get("action") == "skipped")
    failed   = sum(1 for l in logs if l["status"] == "failed")
    pinged   = sum(1 for l in logs if l.get("sitemap_ping"))

    print("\n" + "=" * 60)
    print(f"  ✅ 新規公開        : {inserted} 件")
    print(f"  🔄 Progressive更新 : {updated} 件")
    print(f"  ⏭️  スキップ        : {skipped} 件")
    print(f"  ❌ 失敗            : {failed} 件")
    print(f"  Sitemap ping送信   : {pinged} 回")

    if failed > 0:
        print("\n── 失敗詳細 ──")
        for l in logs:
            if l["status"] == "failed":
                print(f"  [{l['slug']}] {l['reason'][:80]}")


if __name__ == "__main__":
    asyncio.run(main())
