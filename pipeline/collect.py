# -*- coding: utf-8 -*-
"""
Tech Gear Guide — collect.py
RSS収集 → 本文取得 → スコアリング → 重複排除 → collected_articles.jsonl 出力
"""

import asyncio
import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

import feedparser
import httpx
from playwright.async_api import async_playwright

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

try:
    from googlenewsdecoder import gnewsdecoder
    HAS_GNEWS = True
except ImportError:
    HAS_GNEWS = False

# ─────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────

MIN_BODY_LEN        = 500
COLLECT_HOURS       = 24
PLAYWRIGHT_SEM      = 3
OUTPUT_PATH         = Path("collected_articles.jsonl")
CACHE_PATH          = Path("processed_urls_cache.json")
CACHE_MAX           = 2000
PUBLISHED_LOOKBACK_DAYS = 7   # 既投稿記事との重複チェック対象期間

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────────
# MUST_CATCH / LEAK キーワード
# ─────────────────────────────────────────────

MUST_CATCH: dict[str, list[str]] = {
    "smartphone": [
        # Apple
        "iphone 17", "iphone 18", "iphone ultra",
        # Samsung
        "galaxy s26", "galaxy s25", "galaxy z fold 7", "galaxy z fold 6",
        "galaxy z flip 7", "galaxy z flip 6", "galaxy a56", "galaxy a55",
        # Google
        "pixel 10", "pixel 9a", "pixel 9 pro",
        # Sony
        "xperia 1 vii", "xperia 5 vii", "xperia 10 vii",
        "xperia 1 vi", "xperia 5 vi",
        # Motorola
        "motorola edge 60", "motorola razr 2025", "moto g85",
        # Asus
        "zenfone 12", "rog phone 9",
        # Others
        "oneplus 13", "oneplus 13r", "xiaomi 15", "xiaomi 15 ultra",
        "oppo find x8", "realme gt 7", "nothing phone 3",
        "honor 400", "vivo x200",
    ],
    "tablet": [
        "ipad pro", "ipad air", "ipad mini", "ipad 11",
        "galaxy tab s10", "galaxy tab s11", "galaxy tab s10 fe",
        "surface pro 12", "surface pro 11", "surface go 4",
        "pixel tablet 2",
        "lenovo tab p13", "lenovo tab extreme", "xiaomi pad 7",
        "matebook", "matepad",
    ],
    "windows": [
        "windows 12", "windows 11",
        "copilot+ pc", "surface pro", "surface laptop",
        "windows update", "recall",
    ],
    "cpu_gpu": [
        "rtx 5090", "rtx 5080", "rtx 6090", "rtx 6000",
        "rx 9070", "rx 9080",
        "ryzen 9 9000", "core ultra 300",
        "apple m5", "apple m4", "snapdragon x elite", "snapdragon 8 gen 4",
    ],
    "ai": [
        "gpt-5", "gpt-6", "openai",
        "gemini 2.5", "gemini 3",
        "claude 4", "claude opus",
        "llama 4", "llama 5",
        "copilot", "deepmind",
        "sora 2", "veo 3",
    ],
    "xr": [
        "apple vision pro", "apple vision",
        "meta quest 4", "meta quest pro 2", "quest 4",
        "playstation vr3", "psvr3", "sony xr",
        "ar glasses", "smart glasses", "ray-ban meta",
        "google ar", "samsung xr", "mixed reality",
    ],
    "wearable": [
        "apple watch ultra", "apple watch series 11", "apple watch series 10",
        "galaxy watch 8", "galaxy watch ultra 2",
        "pixel watch 4", "pixel watch 3",
        "airpods 4", "airpods pro 3", "airpods max 2",
        "galaxy buds 4", "galaxy buds 3",
        "fitbit", "garmin",
    ],
    "peripheral": [
        # キーボード・マウス
        "mx keys", "mx master", "logitech g pro",
        "razer blackwidow", "razer deathadder",
        "corsair k100", "hyperx alloy",
        # ヘッドフォン・ヘッドセット
        "sony wh-1000xm", "sony wf-1000xm",
        "bose quietcomfort", "jabra evolve",
        # モニター
        "lg ultragear", "samsung odyssey",
        "dell ultrasharp", "asus rog swift",
        # Webカメラ・マイク
        "blue yeti", "elgato facecam",
        # コントローラー
        "dualsense edge", "xbox elite controller",
    ],
    "general": [],
}

_ALL_MUST_CATCH = [kw for kwlist in MUST_CATCH.values() for kw in kwlist]

LEAK_KEYWORDS = [
    "leak", "leaked", "exclusive", "rumor", "rumoured",
    "insider", "reportedly", "allegedly",
    "dummy unit", "hands-on", "render",
    "benchmark", "geekbench", "antutu",
]

# グローバル除外キーワード（全ソース共通・タイトルに含まれる場合スキップ）
GLOBAL_SKIP_KEYWORDS: tuple[str, ...] = (
    # セール・値引き（日本市場との文脈差が大きい）
    "best deals", "deals on", "% off", "percent off",
    "prime day", "black friday", "cyber monday", "price drop",
    "limited time offer", "amazon deal", "amazon sale",
    # 米国通信キャリア固有記事（日本読者に関係なし）
    "verizon", "at&t", "comcast", "xfinity", "boost mobile", "spectrum mobile",
    "t-mobile", "cricket wireless", "us cellular", "metro by t-mobile", "straight talk",
    "tracfone", "consumer cellular", "visible wireless",
    # 米国教育・特定市場向け（日本市場に関係なし）
    "graphing calculator", "ti-84", "ti-83", "ti-89", "casio fx-",
    # 米国規制・行政固有記事
    "fcc ruling", "fcc fine", "fcc approved", "fcc certification",
    # 米国ISP・ケーブル会社
    "cable provider", "cable company", "internet provider",
)

# ─────────────────────────────────────────────
# カテゴリ別バッチ上限
# ─────────────────────────────────────────────

# 1回10記事・1日3回30記事運用: generate.py --max 10 と組み合わせて使用
# 合計21件（バッファ）→ generate.py --max 10 で絞る
CATEGORY_LIMITS: dict[str, int] = {
    "smartphone": 6,   # 重視
    "cpu_gpu":    4,   # 重視
    "windows":    4,   # 重視
    "tablet":     3,   # 重視
    "ai":         2,
    "peripheral": 2,   # 周辺機器・アプリ
    "xr":         1,
    "wearable":   1,
    "general":    3,   # キーワード未分類記事も許容
}

# ─────────────────────────────────────────────
# ソース定義
# ─────────────────────────────────────────────

@dataclass
class Source:
    name: str
    rss: str
    tier: int
    category: str      # キーワード未マッチ時のデフォルト分類（ソースを特定カテゴリに制限しない）
    fetch_method: str
    gnews_rss: str = ""
    skip_keywords: list = field(default_factory=list)


SOURCES: list[Source] = [
    Source("MacRumors",         "https://feeds.macrumors.com/MacRumors-Front",
           tier=2, category="smartphone", fetch_method="rss_full"),
    Source("Android Authority", "https://www.androidauthority.com/feed/",
           tier=1, category="smartphone", fetch_method="httpx"),
    Source("GSMArena",          "https://www.gsmarena.com/rss-news-reviews.php3",
           tier=1, category="smartphone", fetch_method="httpx"),
    Source("Engadget",          "https://www.engadget.com/rss.xml",
           tier=2, category="general",    fetch_method="httpx"),
    Source("Wccftech",          "https://wccftech.com/feed/",
           tier=2, category="cpu_gpu",    fetch_method="httpx"),
    Source("VentureBeat AI",    "https://venturebeat.com/category/ai/feed/",
           tier=2, category="ai",         fetch_method="httpx"),
    Source("TechCrunch AI",     "https://techcrunch.com/category/artificial-intelligence/feed/",
           tier=2, category="ai",         fetch_method="httpx"),
    Source("XDA Developers",    "https://www.xda-developers.com/feed/",
           tier=2, category="smartphone", fetch_method="jina"),
    Source("NotebookCheck",     "https://www.notebookcheck.net/News.152.100.html",
           tier=2, category="cpu_gpu",    fetch_method="jina"),
    Source("Ars Technica",      "https://feeds.arstechnica.com/arstechnica/technology-lab",
           tier=1, category="general",    fetch_method="jina"),
    Source("9to5Mac",           "https://9to5mac.com/feed/",
           tier=1, category="smartphone", fetch_method="playwright"),
    Source("9to5Google",        "https://9to5google.com/feed/",
           tier=1, category="smartphone", fetch_method="playwright"),
    Source("Windows Central",   "https://www.windowscentral.com/rss",
           tier=1, category="windows",    fetch_method="playwright"),
    Source("Tom's Hardware",    "http://www.tomshardware.com/feeds.xml",
           tier=1, category="cpu_gpu",    fetch_method="playwright",
           skip_keywords=["deal", "sale", "coupon", "promo", "best buy"]),
    Source("TechRadar",         "https://www.techradar.com/feeds/articletype/news",
           tier=2, category="general",    fetch_method="playwright",
           skip_keywords=["quordle", "wordle", "nyt", "strands", "connections", "crossword"]),
    Source("The Verge",         "https://www.theverge.com/rss/index.xml",
           tier=1, category="ai",         fetch_method="playwright",
           skip_keywords=["deal", "review roundup", "best"]),
    Source("VideoCardz",        "",
           tier=2, category="cpu_gpu",    fetch_method="playwright",
           gnews_rss="https://news.google.com/rss/search?q=site:videocardz.com&hl=en-US&gl=US&ceid=US:en"),
    Source("Neowin",            "",
           tier=2, category="windows",    fetch_method="playwright",
           gnews_rss="https://news.google.com/rss/search?q=site:neowin.net&hl=en-US&gl=US&ceid=US:en"),
]

# ─────────────────────────────────────────────
# カテゴリ自動補正
# ─────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "smartphone": [
        "iphone", "android", "galaxy", "pixel", "oneplus", "xiaomi", "samsung phone",
        "xperia", "motorola", "moto g", "moto edge", "razr",
        "oppo", "realme", "honor", "vivo",
        "zenfone", "rog phone", "nothing phone",
        "fold", "flip phone", "clamshell phone",
        # スマホアプリ・OS
        "ios 18", "ios 19", "android 15", "android 16",
        "app store", "google play",
        "instagram update", "whatsapp update", "tiktok update",
    ],
    "tablet":     [
        "ipad", "galaxy tab", "surface pro", "surface go", "pixel tablet", "android tablet",
        "lenovo tab", "xiaomi pad", "matepad", "fire tablet",
        "drawing tablet", "e-ink tablet",
    ],
    "windows":    ["windows", "surface laptop", "copilot+", "microsoft pc", "windows update"],
    "cpu_gpu":    ["gpu", "cpu", "rtx", "rx ", "radeon", "geforce", "ryzen", "core ultra",
                   "snapdragon", "apple m", "benchm"],
    "ai":         ["chatgpt", "openai", "gemini", "claude", "llama", "copilot", "deepmind",
                   "llm", "ai model", "gpt-", "sora", "midjourney", "stable diffusion"],
    "xr":         ["vision pro", "meta quest", "vr headset", "ar glasses", "mixed reality",
                   "virtual reality", "augmented reality", "hololens", "psvr"],
    "wearable":   ["apple watch", "galaxy watch", "pixel watch", "smartwatch", "airpods",
                   "galaxy buds", "fitness tracker", "earbuds"],
    "peripheral": [
        # キーボード・マウス
        "mechanical keyboard", "wireless keyboard", "gaming keyboard",
        "gaming mouse", "wireless mouse", "trackpad",
        "logitech", "logicool", "razer", "corsair", "hyperx", "steelseries",
        # ヘッドフォン・スピーカー
        "headphone", "headset", "noise cancell",
        "sony wh", "sony wf", "bose quietcomfort", "jabra",
        # モニター・ディスプレイ
        "gaming monitor", "oled monitor", "4k monitor", "ultrawide",
        # Webカメラ・マイク・配信機器
        "webcam", "stream deck", "capture card", "blue yeti",
        # ゲームコントローラー
        "dualsense", "xbox controller", "pro controller",
        # USB・充電
        "usb hub", "usb-c hub", "docking station", "wireless charger",
    ],
}

def infer_category(title: str, default_cat: str) -> str:
    t = title.lower()
    for cat, kws in _CATEGORY_KEYWORDS.items():
        if any(k in t for k in kws):
            return cat
    return default_cat

# ─────────────────────────────────────────────
# データ型
# ─────────────────────────────────────────────

@dataclass
class RawArticle:
    url: str
    title: str
    body: str
    source_name: str
    tier: int
    category: str
    published: str
    fetch_method_used: str
    body_len: int = 0
    is_leak: bool = False
    is_must_catch: bool = False
    score: float = 0.0
    url_hash: str = ""

    def __post_init__(self):
        self.body_len      = len(self.body)
        self.is_leak       = _detect_leak(self.title)
        self.is_must_catch = _detect_must_catch(self.title)
        self.score         = _calc_score(self)
        self.url_hash      = hashlib.md5(self.url.encode()).hexdigest()[:12]

# ─────────────────────────────────────────────
# スコアリング
# ─────────────────────────────────────────────

def _detect_leak(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in LEAK_KEYWORDS)

def _detect_must_catch(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in _ALL_MUST_CATCH)

def _calc_score(a: RawArticle) -> float:
    score  = (4 - a.tier) * 10
    score += min(a.body_len / 100, 20)
    if a.is_leak:      score += 5
    if a.is_must_catch: score += 15
    return round(score, 2)

# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────

def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

_STOPWORDS: frozenset[str] = frozenset({
    "the", "this", "that", "with", "from", "about", "have", "will", "into",
    "been", "what", "when", "how", "its", "new", "for", "and", "but", "not",
    "are", "all", "can", "has", "get", "out", "one", "more", "also", "than",
    "via", "after", "over", "just", "your", "here", "our", "their", "says",
    "said", "could", "would", "should", "may", "might", "now", "then", "them",
    "these", "those", "some", "while", "next", "back", "first", "last",
    "already", "still", "even", "both", "only", "under", "well", "down",
    "report", "latest", "update", "official", "confirmed", "launch", "launches",
    "launched", "feature", "features", "detail", "details", "reveal", "reveals",
})

def _title_tokens(title: str) -> frozenset[str]:
    words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    return frozenset(w for w in words if len(w) >= 3 and w not in _STOPWORDS)

def _is_topic_dup(tokens: frozenset[str], seen: list[frozenset[str]], threshold: float = 0.6) -> bool:
    if len(tokens) < 2:
        return False
    for s in seen:
        if len(s) < 2:
            continue
        if len(tokens & s) / min(len(tokens), len(s)) >= threshold:
            return True
    return False

def _parse_published(entry) -> Optional[datetime]:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def _is_within_24h(pub_dt: Optional[datetime]) -> bool:
    if pub_dt is None:
        return True
    return (datetime.now(timezone.utc) - pub_dt) < timedelta(hours=COLLECT_HOURS)

# ─────────────────────────────────────────────
# 処理済みURLキャッシュ
# ─────────────────────────────────────────────

def fetch_published_titles() -> list[frozenset[str]]:
    """Supabaseから直近PUBLISHED_LOOKBACK_DAYS日分の公開済みタイトルのトークンセットを取得。"""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return []
    try:
        from datetime import timezone as _tz
        since = (datetime.now(_tz.utc) - timedelta(days=PUBLISHED_LOOKBACK_DAYS)).isoformat()
        headers = {
            "apikey":        key,
            "Authorization": f"Bearer {key}",
        }
        params = {
            "select":         "title",
            "is_published":   "eq.true",
            "published_at":   f"gte.{since}",
            "limit":          "500",
        }
        resp = httpx.get(f"{url}/rest/v1/articles", headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            titles = [row["title"] for row in resp.json() if row.get("title")]
            tokens = [_title_tokens(t) for t in titles]
            print(f"既投稿タイトル取得: {len(tokens)} 件（過去{PUBLISHED_LOOKBACK_DAYS}日）")
            return tokens
    except Exception as e:
        print(f"  ⚠️  既投稿タイトル取得失敗（スキップ）: {e}")
    return []


def load_processed_urls() -> set[str]:
    if CACHE_PATH.exists():
        return set(json.loads(CACHE_PATH.read_text(encoding="utf-8")))
    return set()

def save_processed_urls(urls: set[str]) -> None:
    existing = load_processed_urls()
    merged   = list(existing | urls)
    if len(merged) > CACHE_MAX:
        merged = merged[-CACHE_MAX:]
    CACHE_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

# ─────────────────────────────────────────────
# RSS収集
# ─────────────────────────────────────────────

def collect_rss(src: Source, processed_urls: set[str]) -> list[dict]:
    feed  = feedparser.parse(src.rss)
    items = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title or any(k in title.lower() for k in src.skip_keywords):
            continue
        url = entry.get("link", "")
        if url in processed_urls:
            continue
        pub_dt = _parse_published(entry)
        if not _is_within_24h(pub_dt):
            continue

        body = ""
        if hasattr(entry, "content") and entry.content:
            body = entry.content[0].get("value", "")
        if not body:
            body = entry.get("summary", "")
        body      = _strip_html(body)
        published = pub_dt.isoformat() if pub_dt else datetime.now(timezone.utc).isoformat()
        items.append({"url": url, "title": title, "body": body, "published": published})
    return items

def collect_via_gnews(src: Source, processed_urls: set[str]) -> list[dict]:
    if not HAS_GNEWS or not src.gnews_rss:
        return []
    feed  = feedparser.parse(src.gnews_rss)
    items = []
    for entry in feed.entries[:25]:
        gnews_url = entry.get("link", "")
        if not gnews_url:
            continue
        pub_dt = _parse_published(entry)
        if not _is_within_24h(pub_dt):
            continue
        try:
            result   = gnewsdecoder(gnews_url, interval=1)
            real_url = result.get("decoded_url", "")
            if not real_url or real_url in processed_urls:
                continue
        except Exception:
            continue
        title     = entry.get("title", "").strip()
        published = pub_dt.isoformat() if pub_dt else datetime.now(timezone.utc).isoformat()
        items.append({"url": real_url, "title": title, "body": "", "published": published})
        time.sleep(0.5)
    return items

# ─────────────────────────────────────────────
# 本文取得
# ─────────────────────────────────────────────

def fetch_httpx(url: str) -> Optional[str]:
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code != 200:
                return None
            for pat in [r"<article[^>]*>(.*?)</article>", r"<main[^>]*>(.*?)</main>"]:
                m = re.search(pat, r.text, re.DOTALL | re.IGNORECASE)
                if m:
                    t = _strip_html(m.group(1))
                    if len(t) >= MIN_BODY_LEN:
                        return t
    except Exception:
        pass
    return None

def fetch_jina(url: str) -> Optional[str]:
    try:
        with httpx.Client(timeout=25, follow_redirects=True) as c:
            r = c.get(f"https://r.jina.ai/{url}")
            if r.status_code == 200 and len(r.text) >= MIN_BODY_LEN:
                return r.text.strip()
    except Exception:
        pass
    return None

PW_SELECTORS = [
    "article", ".article-body", ".article__body", ".post-content",
    ".entry-content", ".content-body", ".article-content",
    "[class*='article']", "main",
]

async def fetch_playwright(url: str, browser) -> Optional[str]:
    try:
        ctx  = await browser.new_context(
            user_agent=BROWSER_UA,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = await ctx.new_page()
        if HAS_STEALTH:
            await stealth_async(page)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)

        title = await page.title()
        if any(k in title.lower() for k in ["just a moment", "cloudflare", "security check"]):
            await page.wait_for_timeout(5000)

        for sel in PW_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    t = re.sub(r"\s+", " ", await el.inner_text()).strip()
                    if len(t) >= MIN_BODY_LEN:
                        await ctx.close()
                        return t
            except Exception:
                continue

        try:
            t = re.sub(r"\s+", " ", await page.inner_text("body")).strip()
            if len(t) >= MIN_BODY_LEN:
                await ctx.close()
                return t
        except Exception:
            pass
        await ctx.close()
    except Exception:
        pass
    return None

async def fetch_body(url: str, src: Source, rss_body: str, browser) -> tuple[str, str]:
    if src.fetch_method == "rss_full" and len(rss_body) >= MIN_BODY_LEN:
        return rss_body, "rss_full"
    if src.fetch_method in ("httpx", "rss_full"):
        t = fetch_httpx(url)
        if t:
            return t, "httpx"
    if src.fetch_method in ("jina", "httpx", "rss_full"):
        t = fetch_jina(url)
        if t:
            return t, "jina"
    t = await fetch_playwright(url, browser)
    if t:
        return t, "playwright"
    return "", "failed"

# ─────────────────────────────────────────────
# 3層重複排除
# ─────────────────────────────────────────────

def dedup_and_limit(
    articles: list[RawArticle],
    published_tokens: list[frozenset[str]] | None = None,
) -> list[RawArticle]:
    articles    = sorted(articles, key=lambda x: -x.score)
    seen_urls:  set[str]             = set()
    seen_tokens: list[frozenset[str]] = list(published_tokens or [])
    cat_counts: Counter              = Counter()
    result:     list[RawArticle]     = []

    for a in articles:
        if a.url in seen_urls:
            continue
        # グローバル除外キーワードチェック
        title_lower = a.title.lower()
        if any(k in title_lower for k in GLOBAL_SKIP_KEYWORDS):
            continue
        # トークンオーバーラップによる重複検出（バッチ内 + 既投稿記事）
        tokens = _title_tokens(a.title)
        if _is_topic_dup(tokens, seen_tokens):
            continue
        limit = CATEGORY_LIMITS.get(a.category, 3)
        if not a.is_must_catch and cat_counts[a.category] >= limit:
            continue
        seen_urls.add(a.url)
        seen_tokens.append(tokens)
        cat_counts[a.category] += 1
        result.append(a)
    return result

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

async def main():
    processed_urls = load_processed_urls()
    print(f"処理済みURLキャッシュ: {len(processed_urls)} 件")

    all_articles: list[RawArticle] = []
    new_urls: set[str]             = set()
    sem = asyncio.Semaphore(PLAYWRIGHT_SEM)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for src in SOURCES:
            print(f"\n[{src.name}] ({src.category}) 収集中...")
            entries = collect_via_gnews(src, processed_urls) if src.gnews_rss else collect_rss(src, processed_urls)
            print(f"  → {len(entries)} 件（24h以内・未処理）")

            async def process(entry: dict, _src: Source = src) -> Optional[RawArticle]:
                async with sem:
                    body, method = await fetch_body(entry["url"], _src, entry["body"], browser)
                    if not body:
                        return None
                    cat = infer_category(entry["title"], _src.category)
                    art = RawArticle(
                        url=entry["url"], title=entry["title"], body=body,
                        source_name=_src.name, tier=_src.tier, category=cat,
                        published=entry["published"], fetch_method_used=method,
                    )
                    flag = "🔴 MUST_CATCH" if art.is_must_catch else ("🟡 LEAK" if art.is_leak else "")
                    print(f"    ✅ [{method}] {len(body):,}字 {flag} : {entry['title'][:55]}")
                    return art

            results = await asyncio.gather(*[process(e) for e in entries])
            for a in results:
                if a:
                    all_articles.append(a)
                    new_urls.add(a.url)

        await browser.close()

    published_tokens = fetch_published_titles()
    deduped = dedup_and_limit(all_articles, published_tokens)
    print(f"\n重複排除・上限適用: {len(all_articles)} → {len(deduped)} 件")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for a in deduped:
            f.write(json.dumps(asdict(a), ensure_ascii=False) + "\n")

    save_processed_urls(new_urls)
    print(f"キャッシュ更新: +{len(new_urls)} URL")

    print("\n" + "=" * 60)
    by_cat: dict[str, list[RawArticle]] = defaultdict(list)
    for a in deduped:
        by_cat[a.category].append(a)
    for cat, arts in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat:<12} {len(arts):>3}本  {arts[0].title[:45]}...")
    print(f"\n合計: {len(deduped)} 件  "
          f"(MUST_CATCH: {sum(1 for a in deduped if a.is_must_catch)}, "
          f"LEAK: {sum(1 for a in deduped if a.is_leak)})")

    mc = [a for a in deduped if a.is_must_catch]
    if mc:
        print("\n── MUST_CATCH ──")
        for a in mc:
            print(f"  [{a.source_name}] {a.title[:65]}")


if __name__ == "__main__":
    asyncio.run(main())
