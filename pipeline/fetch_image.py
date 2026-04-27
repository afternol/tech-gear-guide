# -*- coding: utf-8 -*-
"""
Tech Gear Guide — fetch_image.py
アイキャッチ画像の取得: Unsplash API → カテゴリフォールバック
"""

import os
import hashlib
from pathlib import Path
from typing import Optional
import httpx

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
IMG_DIR             = Path("tmp_images")
IMG_DIR.mkdir(exist_ok=True)

CATEGORY_QUERIES: dict[str, str] = {
    "smartphone": "smartphone closeup mobile phone",
    "tablet":     "tablet device ipad",
    "windows":    "laptop windows computer screen",
    "cpu_gpu":    "computer chip gpu graphics card",
    "ai":         "artificial intelligence neural network",
    "xr":         "virtual reality headset ar glasses",
    "wearable":   "smartwatch wearable technology",
    "general":    "technology electronics gadget",
}

FALLBACK_IMAGES: dict[str, str] = {
    "smartphone": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200",
    "tablet":     "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=1200",
    "windows":    "https://images.unsplash.com/photo-1484788984921-03950022c9ef?w=1200",
    "cpu_gpu":    "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=1200",
    "ai":         "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=1200",
    "xr":         "https://images.unsplash.com/photo-1617802690992-15d93263d3a9?w=1200",
    "wearable":   "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=1200",
    "general":    "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200",
}


def _download(url: str, dest: Path) -> bool:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code == 200 and len(r.content) > 10_000:
                dest.write_bytes(r.content)
                return True
    except Exception:
        pass
    return False


def fetch_unsplash(query: str, slug: str) -> Optional[dict]:
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 1, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            )
            if r.status_code != 200:
                return None
            results = r.json().get("results", [])
            if not results:
                return None
            photo    = results[0]
            img_url  = photo["urls"]["regular"] + "&w=1200&q=80"
            credit   = f"Photo by {photo['user']['name']} on Unsplash"
            dest     = IMG_DIR / f"{slug}.jpg"
            if _download(img_url, dest):
                return {
                    "local_path": str(dest),
                    "source":     "unsplash",
                    "credit":     credit,
                    "url":        img_url,
                }
    except Exception:
        pass
    return None


def fetch_fallback(category: str, slug: str) -> dict:
    url  = FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["general"])
    dest = IMG_DIR / f"{slug}.jpg"
    _download(url, dest)
    return {
        "local_path": str(dest) if dest.exists() else "",
        "source":     "fallback",
        "credit":     "Tech Gear Guide",
        "url":        url,
    }


def fetch_article_image(
    title: str,
    category: str,
    article_type: str,
    slug: str,
) -> dict:
    query = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["general"])

    result = fetch_unsplash(query, slug)
    if result:
        return result

    return fetch_fallback(category, slug)
