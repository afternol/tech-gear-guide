# -*- coding: utf-8 -*-
"""
Tech Gear Guide — fetch_image.py
アイキャッチ画像の取得: Unsplash API（記事別クエリ） → Pexels API → カテゴリフォールバック
"""

import os
import re
from pathlib import Path
from typing import Optional
import httpx

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY", "")
IMG_DIR             = Path("tmp_images")
IMG_DIR.mkdir(exist_ok=True)

# ── カテゴリ別フォールバック ──────────────────────────────────

CATEGORY_QUERIES: dict[str, str] = {
    "smartphone": "smartphone mobile phone technology",
    "tablet":     "tablet device ipad technology",
    "windows":    "laptop windows computer desk",
    "cpu_gpu":    "computer chip gpu processor silicon",
    "ai":         "artificial intelligence neural network data",
    "xr":         "virtual reality headset ar glasses",
    "wearable":   "smartwatch wearable fitness tracker",
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

# ── クエリ生成 ────────────────────────────────────────────────

_EN_STOP = {
    'the','a','an','is','are','was','were','be','been','have','has','had',
    'do','does','did','will','would','could','should','may','might','can',
    'of','in','on','at','to','for','with','by','from','as','into','about',
    'than','after','before','and','or','but','not','if','this','that','it',
    'its','how','what','why','when','which','who','new','now','get','just',
    'use','using','used','via','vs','vs.','more','most','best','top',
}

# カテゴリ補助ワード（クエリ末尾に加えて検索の文脈を補強）
_CAT_CONTEXT: dict[str, str] = {
    "smartphone": "smartphone",
    "tablet":     "tablet",
    "windows":    "windows PC",
    "cpu_gpu":    "processor chip",
    "ai":         "AI technology",
    "xr":         "VR AR headset",
    "wearable":   "wearable smartwatch",
    "general":    "technology",
}


def build_search_query(title: str, tags: list[str], category: str) -> str:
    """
    タイトル・タグ・カテゴリからUnsplash/Pexels検索クエリを生成する。
    英数字のプロダクト名・ブランド名を優先して抽出する。
    """
    # タイトルから英数字トークンを抽出（製品名・ブランド名が多い）
    title_tokens = re.findall(r'[A-Za-z][a-zA-Z0-9+\-]{1,}', title)
    title_words  = [w for w in title_tokens if w.lower() not in _EN_STOP and len(w) >= 3]

    # タグから英字タグを抽出
    tag_words = [t for t in tags if re.match(r'^[a-zA-Z]', t) and t.lower() not in _EN_STOP]

    # 合成: タイトル先頭3語 + タグ先頭2語
    parts = title_words[:3] + tag_words[:2]

    if not parts:
        # 英字が全くない場合（日本語タイトルのみ）はカテゴリクエリで代替
        return CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["general"])

    context = _CAT_CONTEXT.get(category, "technology")
    query   = " ".join(parts) + " " + context
    return query[:80]


# ── ダウンロード ──────────────────────────────────────────────

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


# ── Unsplash ──────────────────────────────────────────────────

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
            photo   = results[0]
            img_url = photo["urls"]["regular"] + "&w=1200&q=80"
            credit  = f"Photo by {photo['user']['name']} on Unsplash"
            dest    = IMG_DIR / f"{slug}.jpg"
            if _download(img_url, dest):
                return {"local_path": str(dest), "source": "unsplash", "credit": credit, "url": img_url}
    except Exception:
        pass
    return None


# ── Pexels ────────────────────────────────────────────────────

def fetch_pexels(query: str, slug: str) -> Optional[dict]:
    if not PEXELS_API_KEY:
        return None
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 1, "orientation": "landscape"},
                headers={"Authorization": PEXELS_API_KEY},
            )
            if r.status_code != 200:
                return None
            photos = r.json().get("photos", [])
            if not photos:
                return None
            photo   = photos[0]
            img_url = photo["src"]["large2x"]
            credit  = f"Photo by {photo['photographer']} on Pexels"
            dest    = IMG_DIR / f"{slug}.jpg"
            if _download(img_url, dest):
                return {"local_path": str(dest), "source": "pexels", "credit": credit, "url": img_url}
    except Exception:
        pass
    return None


# ── フォールバック ────────────────────────────────────────────

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


# ── メインエントリ ────────────────────────────────────────────

def fetch_article_image(
    title:        str,
    category:     str,
    article_type: str,
    slug:         str,
    tags:         list[str] | None = None,
) -> dict:
    query = build_search_query(title, tags or [], category)

    result = fetch_unsplash(query, slug)
    if result:
        return result

    result = fetch_pexels(query, slug)
    if result:
        return result

    # カテゴリクエリで再試行（タイトルベースで結果がなかった場合）
    if query != CATEGORY_QUERIES.get(category, ""):
        cat_query = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["general"])
        result = fetch_unsplash(cat_query, slug) or fetch_pexels(cat_query, slug)
        if result:
            return result

    return fetch_fallback(category, slug)
