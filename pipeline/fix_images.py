# -*- coding: utf-8 -*-
"""
Tech Gear Guide — fix_images.py
featured_image_url が空の既存記事にカテゴリ別フォールバック画像を設定する

使い方:
  cd pipeline
  python fix_images.py            # 実際に更新
  python fix_images.py --dry-run  # 対象記事を確認するだけ
"""

import os
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from supabase import create_client
except ImportError:
    print("supabase パッケージが必要です: pip install supabase")
    sys.exit(1)

from fetch_image import FALLBACK_IMAGES, fetch_unsplash, CATEGORY_QUERIES

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DRY_RUN      = "--dry-run" in sys.argv


def main():
    if DRY_RUN:
        print("=== DRY-RUN モード ===")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # featured_image_url が空の記事を取得
    res = sb.table("articles").select(
        "slug,title,category,featured_image_url"
    ).eq("is_published", True).execute()

    targets = [a for a in (res.data or []) if not a.get("featured_image_url")]
    print(f"画像なし記事: {len(targets)} 件")

    if not targets:
        print("修正対象なし")
        return

    updated = 0
    for a in targets:
        slug     = a["slug"]
        category = a["category"]

        # Unsplashから取得を試みる（UNSPLASH_ACCESS_KEY があれば）
        img_url = ""
        result = fetch_unsplash(CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["general"]), slug)
        if result:
            img_url = result["url"]
            credit  = result["credit"]
            source  = "unsplash"
        else:
            img_url = FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["general"])
            credit  = "Tech Gear Guide"
            source  = "fallback"

        print(f"  {'[DRY] ' if DRY_RUN else ''}更新: {slug[:50]} [{category}] → {source}")

        if not DRY_RUN:
            sb.table("articles").update({
                "featured_image_url":    img_url,
                "featured_image_source": source,
                "featured_image_credit": credit,
            }).eq("slug", slug).execute()
            updated += 1

    print(f"\n{'確認' if DRY_RUN else '更新'}完了: {len(targets) if DRY_RUN else updated} 件")


if __name__ == "__main__":
    main()
