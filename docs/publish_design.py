# -*- coding: utf-8 -*-
"""
DeviceBrief publish.py 設計ドラフト v2

入力: generated_articles.jsonl（generate.pyの出力）
処理:
  1. fetch_image.py を呼び出してアイキャッチ画像を取得・生成
  2. 画像を Supabase Storage にアップロード
  3. Supabase articles テーブルに INSERT（新規）または PATCH（Progressive更新）
  4. Next.js ISR revalidate エンドポイントをコール
  5. Sitemap ping（C型/MUST_CATCH新記事・Progressive大型更新時のみ）
  6. 公開ログを published_log.jsonl に追記

Progressive Article のURL発行ルール（仕様書15章・戦略2準拠）:
  - A型速報          → 新URL（INSERT）
  - B型深掘り続報    → 同URL更新（PATCH）。progressive_phase フィールドで判定
  - C型/MUST_CATCH   → 常に新URL（INSERT）。Sitemap pingを必ず送信
"""

import asyncio
import json
import sys
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

from fetch_image import fetch_article_image

# ─────────────────────────────────────────────
# 設定（本番は .env から読み込む）
# ─────────────────────────────────────────────

import os
SUPABASE_URL             = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY     = os.getenv("SUPABASE_SERVICE_KEY", "")
NEXTJS_REVALIDATE_URL    = os.getenv("NEXTJS_REVALIDATE_URL", "")
NEXTJS_REVALIDATE_SECRET = os.getenv("NEXTJS_REVALIDATE_SECRET", "")
SITE_SITEMAP_URL         = os.getenv("SITE_SITEMAP_URL", "")  # https://devicebrief.com/sitemap.xml

INPUT_PATH   = Path("generated_articles.jsonl")
LOG_PATH     = Path("published_log.jsonl")
MAX_PARALLEL = 5

# Progressive大型更新の判定閾値（前版の文字数に対する倍率）
MAJOR_UPDATE_RATIO = 1.5

# ─────────────────────────────────────────────
# データ型
# ─────────────────────────────────────────────

@dataclass
class ArticleRow:
    """Supabase articles テーブルの1行"""
    title: str
    slug: str
    body: str
    category: str
    tags: list[str]
    article_type: str
    source_reliability: int      # C型のみ 1〜5、それ以外は 0
    sources: list[dict]          # [{title, url, media}]
    featured_image_url: str
    featured_image_source: str
    featured_image_credit: str
    seo_description: str
    published_at: str            # ISO8601
    is_published: bool = True
    is_must_catch: bool = False
    is_leak: bool = False
    progressive_phase: Optional[int] = None   # 1=速報 / 2=詳細 / 3=決定版（nullは通常記事）
    last_major_update_at: Optional[str] = None

# ─────────────────────────────────────────────
# Supabase ヘルパー
# ─────────────────────────────────────────────

def _supabase_headers(prefer: str = "return=minimal") -> dict:
    return {
        "apikey":        SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        prefer,
    }

def slug_exists(slug: str) -> tuple[bool, str]:
    """
    slugが既存かどうかを確認。
    戻り値: (存在フラグ, 既存のbody文字列 or "")
    """
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                f"{SUPABASE_URL}/rest/v1/articles",
                headers=_supabase_headers(),
                params={"slug": f"eq.{slug}", "select": "id,body"},
            )
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return True, data[0].get("body", "")
            return False, ""
    except Exception:
        return False, ""

def insert_article(row: ArticleRow) -> tuple[bool, str]:
    """Supabase に記事をINSERT。戻り値: (成功フラグ, エラーメッセージ or "")"""
    payload = {
        "title":                  row.title,
        "slug":                   row.slug,
        "body":                   row.body,
        "category":               row.category,
        "tags":                   row.tags,
        "article_type":           row.article_type,
        "source_reliability":     row.source_reliability,
        "sources":                row.sources,
        "featured_image_url":     row.featured_image_url,
        "featured_image_source":  row.featured_image_source,
        "featured_image_credit":  row.featured_image_credit,
        "seo_description":        row.seo_description,
        "published_at":           row.published_at,
        "is_published":           row.is_published,
        "is_must_catch":          row.is_must_catch,
        "is_leak":                row.is_leak,
        "progressive_phase":      row.progressive_phase,
        "last_major_update_at":   row.last_major_update_at,
    }
    try:
        with httpx.Client(timeout=15) as c:
            r = c.post(
                f"{SUPABASE_URL}/rest/v1/articles",
                headers=_supabase_headers(),
                json=payload,
            )
            if r.status_code in (200, 201):
                return True, ""
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

def update_article(slug: str, updates: dict) -> tuple[bool, str]:
    """
    Progressive更新: 既存記事をPATCH。
    updates には body・progressive_phase・last_major_update_at 等を渡す。
    """
    try:
        with httpx.Client(timeout=15) as c:
            r = c.patch(
                f"{SUPABASE_URL}/rest/v1/articles",
                headers=_supabase_headers(),
                params={"slug": f"eq.{slug}"},
                json=updates,
            )
            if r.status_code in (200, 204):
                return True, ""
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

# ─────────────────────────────────────────────
# Supabase Storage — 画像アップロード
# ─────────────────────────────────────────────

STORAGE_BUCKET = "article-images"

def upload_image(local_path: str, slug: str) -> Optional[str]:
    """ローカル画像ファイルを Supabase Storage にアップロード。戻り値: 公開URL or None"""
    file_path = Path(local_path)
    if not file_path.exists():
        return None

    storage_key = f"thumbnails/{slug}.jpg"
    upload_url  = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_key}"
    public_url  = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_key}"

    try:
        with httpx.Client(timeout=30) as c:
            with open(file_path, "rb") as f:
                r = c.post(
                    upload_url,
                    headers={
                        "apikey":        SUPABASE_SERVICE_KEY,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                        "Content-Type":  "image/jpeg",
                        "x-upsert":      "true",
                    },
                    content=f.read(),
                )
            if r.status_code in (200, 201):
                return public_url
            print(f"  ⚠️  画像アップロード失敗: HTTP {r.status_code}")
            return None
    except Exception as e:
        print(f"  ⚠️  画像アップロードエラー: {e}")
        return None

# ─────────────────────────────────────────────
# Next.js ISR revalidate
# ─────────────────────────────────────────────

def revalidate(slug: str) -> bool:
    if not NEXTJS_REVALIDATE_URL:
        return True
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                NEXTJS_REVALIDATE_URL,
                params={
                    "secret": NEXTJS_REVALIDATE_SECRET,
                    "path":   f"/articles/{slug}",
                },
            )
            return r.status_code == 200
    except Exception:
        return False

# ─────────────────────────────────────────────
# Sitemap ping
# ─────────────────────────────────────────────

async def ping_sitemap() -> bool:
    """
    Sitemapの更新をGoogleに通知する。
    送信するのは以下2ケースのみ:
      1. C型/MUST_CATCH の新記事公開時
      2. Progressive更新で文字数が前版の MAJOR_UPDATE_RATIO 倍以上になった時
    """
    if not SITE_SITEMAP_URL:
        return True
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://www.google.com/ping",
                params={"sitemap": SITE_SITEMAP_URL},
            )
            return r.status_code == 200
    except Exception:
        return False

def is_major_update(old_body: str, new_body: str) -> bool:
    """文字数が MAJOR_UPDATE_RATIO 倍以上増えた場合を大型更新と判定"""
    old_len = len(old_body)
    if old_len == 0:
        return True
    return len(new_body) / old_len >= MAJOR_UPDATE_RATIO

# ─────────────────────────────────────────────
# 1記事分の処理
# ─────────────────────────────────────────────

async def publish_one(article: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        slug  = article.get("slug", "")
        title = article.get("title", "")
        progressive_phase  = article.get("progressive_phase")   # None or 1/2/3
        is_must_catch      = article.get("is_must_catch", False)
        article_type       = article.get("article_type", "A型速報")

        log_entry = {
            "slug":         slug,
            "title":        title[:60],
            "status":       "failed",
            "reason":       "",
            "action":       "",    # "inserted" / "updated" / "skipped"
            "image_src":    "",
            "sitemap_ping": False,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        # ── 既存チェック ─────────────────────────────
        exists, old_body = slug_exists(slug)

        # Progressive以外の記事が既存 → スキップ
        if exists and progressive_phase is None:
            log_entry["status"] = "skipped"
            log_entry["action"] = "skipped"
            log_entry["reason"] = "slug already exists"
            print(f"  ⏭️  スキップ（重複）: {slug}")
            return log_entry

        new_body       = article.get("body", "")
        needs_ping     = False
        action         = ""

        # ── Progressive更新ルート（B型続報）────────────
        if exists and progressive_phase is not None:
            major = is_major_update(old_body, new_body)
            now   = datetime.now(timezone.utc).isoformat()
            updates = {
                "body":                  new_body,
                "progressive_phase":     progressive_phase,
                "seo_description":       article.get("seo_description", ""),
                "tags":                  article.get("tags", []),
                "sources":               article.get("sources", []),
                "last_major_update_at":  now if major else None,
            }
            ok, err = update_article(slug, updates)
            if not ok:
                log_entry["reason"] = err
                print(f"  ❌ UPDATE失敗: {slug} — {err[:80]}")
                return log_entry

            action     = "updated"
            needs_ping = major
            phase_str  = f"Phase{progressive_phase}"
            print(f"  🔄 Progressive更新（{phase_str}{'・大型' if major else ''}）: {title[:50]}")

        # ── 新規INSERTルート ──────────────────────────
        else:
            img_result     = fetch_article_image(
                title=title,
                category=article.get("category", "general"),
                article_type=article_type,
                slug=slug,
            )
            public_img_url = ""
            if img_result["local_path"]:
                public_img_url = upload_image(img_result["local_path"], slug) or ""

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
                log_entry["reason"] = err
                print(f"  ❌ INSERT失敗: {slug} — {err[:80]}")
                return log_entry

            action     = "inserted"
            log_entry["image_src"] = img_result.get("source", "")
            # C型/MUST_CATCHの新記事は必ずpingを送る
            needs_ping = is_must_catch or "C型" in article_type
            print(f"  ✅ 公開: {title[:55]}")

        # ── ISR revalidate ────────────────────────────
        revalidate(slug)

        # ── Sitemap ping ──────────────────────────────
        if needs_ping:
            pinged = await ping_sitemap()
            log_entry["sitemap_ping"] = pinged

        log_entry["status"] = "published"
        log_entry["action"] = action
        return log_entry

# ─────────────────────────────────────────────
# メイン処理
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

    sem   = asyncio.Semaphore(MAX_PARALLEL)
    tasks = [publish_one(a, sem) for a in articles]
    logs  = await asyncio.gather(*tasks)

    # ── ログ追記 ──────────────────────────────────────
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for log in logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")

    # ── サマリー ──────────────────────────────────────
    inserted     = sum(1 for l in logs if l.get("action") == "inserted")
    updated      = sum(1 for l in logs if l.get("action") == "updated")
    skipped      = sum(1 for l in logs if l.get("action") == "skipped")
    failed       = sum(1 for l in logs if l["status"] == "failed")
    press_img    = sum(1 for l in logs if l.get("image_src") == "press")
    unsplash_img = sum(1 for l in logs if l.get("image_src") == "unsplash")
    pinged       = sum(1 for l in logs if l.get("sitemap_ping"))

    print("\n" + "=" * 60)
    print("投稿サマリー")
    print("=" * 60)
    print(f"  ✅ 新規公開          : {inserted} 件")
    print(f"  🔄 Progressive更新   : {updated} 件")
    print(f"  ⏭️  スキップ（重複）  : {skipped} 件")
    print(f"  ❌ 失敗              : {failed} 件")
    print(f"  画像（プレス）       : {press_img} 件")
    print(f"  画像（Unsplash）     : {unsplash_img} 件")
    print(f"  Sitemap ping送信     : {pinged} 回")
    print(f"  ログ: {LOG_PATH}")

    if failed > 0:
        print("\n── 失敗詳細 ──")
        for l in logs:
            if l["status"] == "failed":
                print(f"  [{l['slug']}] {l['reason'][:80]}")


if __name__ == "__main__":
    asyncio.run(main())
