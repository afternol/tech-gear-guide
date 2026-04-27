# -*- coding: utf-8 -*-
"""
Tech Gear Guide — fix_images.py
featured_image_url が空（またはfallback）の既存記事に記事別画像を設定する

使い方:
  cd pipeline
  python fix_images.py            # 画像なし記事のみ更新
  python fix_images.py --all      # fallback画像も含めて全記事を再取得
  python fix_images.py --dry-run  # 対象を確認するだけ
"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(".env")
except ImportError:
    pass

import httpx
from fetch_image import fetch_article_image, FALLBACK_IMAGES

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DRY_RUN      = "--dry-run" in sys.argv
ALL_MODE     = "--all"      in sys.argv   # fallback画像も再取得


def _headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
    }


def fetch_all_articles() -> list[dict]:
    with httpx.Client(timeout=15) as c:
        r = c.get(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=_headers(),
            params={"select": "slug,title,category,tags,featured_image_url,featured_image_source",
                    "is_published": "eq.true"},
        )
        r.raise_for_status()
        return r.json()


def patch_article(slug: str, payload: dict) -> bool:
    with httpx.Client(timeout=15) as c:
        r = c.patch(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=_headers(),
            params={"slug": f"eq.{slug}"},
            json=payload,
        )
        return r.status_code in (200, 204)


def is_fallback_url(url: str) -> bool:
    return url in FALLBACK_IMAGES.values()


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL / SUPABASE_SERVICE_KEY が未設定です")
        sys.exit(1)

    mode = "ALL（fallback含む再取得）" if ALL_MODE else "画像なしのみ"
    if DRY_RUN:
        print(f"=== DRY-RUN モード / 対象: {mode} ===")
    else:
        print(f"=== 対象: {mode} ===")

    articles = fetch_all_articles()

    if ALL_MODE:
        targets = [a for a in articles if not a.get("featured_image_url") or is_fallback_url(a.get("featured_image_url", ""))]
    else:
        targets = [a for a in articles if not a.get("featured_image_url")]

    print(f"全記事: {len(articles)}件 / 更新対象: {len(targets)}件")
    if not targets:
        print("修正対象なし")
        return

    updated = skipped = 0
    for a in targets:
        slug     = a["slug"]
        category = a["category"]
        title    = a["title"]
        tags     = a.get("tags") or []

        result = fetch_article_image(
            title=title,
            category=category,
            article_type="A型速報",
            slug=slug,
            tags=tags,
        )
        source = result.get("source", "fallback")
        img_url = result.get("url", "")

        # fallbackしか取れなかった場合はスキップ（--allモード以外）
        if not ALL_MODE and source == "fallback" and is_fallback_url(img_url):
            print(f"  [SKIP] {slug[:45]} — API未設定のためfallbackのみ")
            skipped += 1
            continue

        print(f"  {'[DRY] ' if DRY_RUN else ''}更新: {slug[:45]} [{category}] → {source}")

        if not DRY_RUN:
            ok = patch_article(slug, {
                "featured_image_url":    img_url,
                "featured_image_source": source,
                "featured_image_credit": result.get("credit", "Tech Gear Guide"),
            })
            if ok:
                updated += 1
            else:
                print(f"    ⚠️  更新失敗: {slug}")

    if DRY_RUN:
        print(f"\n確認完了: {len(targets)}件")
    else:
        print(f"\n更新完了: {updated}件 / スキップ: {skipped}件")


if __name__ == "__main__":
    main()
