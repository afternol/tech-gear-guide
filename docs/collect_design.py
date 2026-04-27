# -*- coding: utf-8 -*-
"""
DeviceBrief collect.py 設計ドラフト v2
SmaTechのcollect.pyをDeviceBrief向けに全面改造

変更点 (v2):
  - カテゴリ: tablet / ai 追加（合計6カテゴリ）
  - 24時間以内の記事のみ対象
  - 3層重複防止（URL / タイトルFP / 主要キーワード）
  - MUST_CATCHキーワード監視（リーク・主要製品は絶対取りこぼさない）
  - カテゴリ別上限（偏重防止）
  - 処理済みURLキャッシュ（バッチ間重複防止）
  - AIソース追加（VentureBeat / The Verge / TechCrunch）
"""

import asyncio
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

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

MIN_BODY_LEN   = 500         # これ未満はスキップ
COLLECT_HOURS  = 24          # 24時間以内の記事のみ対象
PLAYWRIGHT_SEM = 3           # Playwright同時実行数
OUTPUT_PATH    = Path("collected_articles.jsonl")
CACHE_PATH     = Path("processed_urls_cache.json")  # 処理済みURLキャッシュ
CACHE_MAX      = 2000        # キャッシュ保持URL数（48時間分相当）

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
        "iphone 17", "iphone 18", "iphone ultra",
        "galaxy s26", "galaxy z fold 7", "galaxy z flip 7",
        "pixel 10", "pixel 9a",
        "oneplus 13", "xiaomi 15",
    ],
    "tablet": [
        "ipad pro", "ipad air", "ipad mini",
        "galaxy tab s10", "galaxy tab s11",
        "surface pro 12", "surface pro 11",
        "pixel tablet 2",
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
    "general": [],
}

# 全カテゴリのMUST_CATCHフラットリスト（判定用）
_ALL_MUST_CATCH = [kw for kwlist in MUST_CATCH.values() for kw in kwlist]

LEAK_KEYWORDS = [
    "leak", "leaked", "exclusive", "rumor", "rumoured",
    "insider", "reportedly", "allegedly",
    "dummy unit", "hands-on", "render",
    "benchmark", "geekbench", "antutu",
]

# ─────────────────────────────────────────────
# カテゴリ別バッチ上限（MUST_CATCHは無視）
# ─────────────────────────────────────────────

CATEGORY_LIMITS: dict[str, int] = {
    "smartphone": 7,
    "ai":         4,
    "cpu_gpu":    4,
    "windows":    3,
    "tablet":     2,
    "xr":         2,
    "wearable":   2,
    "general":    2,
}

# ─────────────────────────────────────────────
# ソース定義
# ─────────────────────────────────────────────

@dataclass
class Source:
    name: str
    rss: str
    tier: int            # 1=最重要 / 2=重要
    category: str        # smartphone / tablet / windows / cpu_gpu / ai / general
    fetch_method: str    # rss_full / httpx / jina / playwright
    gnews_rss: str = ""  # VideoCardz / Neowin 用
    skip_keywords: list = field(default_factory=list)


SOURCES: list[Source] = [
    # ── RSS本文あり ─────────────────────────────────────
    Source("MacRumors",         "https://feeds.macrumors.com/MacRumors-Front",
           tier=2, category="smartphone", fetch_method="rss_full"),

    # ── httpx直接 ──────────────────────────────────────
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

    # ── Jina Reader ────────────────────────────────────
    Source("XDA Developers",    "https://www.xda-developers.com/feed/",
           tier=2, category="smartphone", fetch_method="jina"),
    Source("NotebookCheck",     "https://www.notebookcheck.net/News.152.100.html",
           tier=2, category="cpu_gpu",    fetch_method="jina"),
    Source("Ars Technica",      "https://feeds.arstechnica.com/arstechnica/technology-lab",
           tier=1, category="general",    fetch_method="jina"),

    # ── Playwright(stealth) ────────────────────────────
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

    # ── googlenewsdecoder + Playwright ────────────────
    Source("VideoCardz",        "",
           tier=2, category="cpu_gpu",    fetch_method="playwright",
           gnews_rss="https://news.google.com/rss/search?q=site:videocardz.com&hl=en-US&gl=US&ceid=US:en"),
    Source("Neowin",            "",
           tier=2, category="windows",    fetch_method="playwright",
           gnews_rss="https://news.google.com/rss/search?q=site:neowin.net&hl=en-US&gl=US&ceid=US:en"),
]

# ─────────────────────────────────────────────
# カテゴリ自動補正（The Verge等は記事内容でカテゴリを再判定）
# ─────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "smartphone": ["iphone", "android", "galaxy", "pixel", "oneplus", "xiaomi", "samsung phone"],
    "tablet":     ["ipad", "galaxy tab", "surface pro", "surface go", "pixel tablet", "android tablet"],
    "windows":    ["windows", "surface laptop", "copilot+", "microsoft pc", "windows update"],
    "cpu_gpu":    ["gpu", "cpu", "rtx", "rx ", "radeon", "geforce", "ryzen", "core ultra",
                   "snapdragon", "apple m", "benchm"],
    "ai":         ["chatgpt", "openai", "gemini", "claude", "llama", "copilot", "deepmind",
                   "llm", "ai model", "gpt-", "sora", "midjourney", "stable diffusion"],
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
        self.body_len     = len(self.body)
        self.is_leak      = _detect_leak(self.title)
        self.is_must_catch = _detect_must_catch(self.title)
        self.score        = _calc_score(self)
        self.url_hash     = hashlib.md5(self.url.encode()).hexdigest()[:12]

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
    score = 0.0
    score += (4 - a.tier) * 10           # Tier1=30, Tier2=20
    score += min(a.body_len / 100, 20)   # 本文長ボーナス（最大20）
    if a.is_leak:
        score += 5
    if a.is_must_catch:
        score += 15                       # 主要製品・キーワードは最優先
    return round(score, 2)

# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────

def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

def _title_fingerprint(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())

def _parse_published(entry) -> Optional[datetime]:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def _is_within_24h(pub_dt: Optional[datetime]) -> bool:
    if pub_dt is None:
        return True  # 日時不明は通す
    return (datetime.now(timezone.utc) - pub_dt) < timedelta(hours=COLLECT_HOURS)

# ─────────────────────────────────────────────
# 処理済みURLキャッシュ（バッチ間重複防止）
# ─────────────────────────────────────────────

def load_processed_urls() -> set[str]:
    if CACHE_PATH.exists():
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return set(data)
    return set()

def save_processed_urls(urls: set[str]) -> None:
    existing = load_processed_urls()
    merged = list(existing | urls)
    # 上限超えたら古い方（先頭）を削除
    if len(merged) > CACHE_MAX:
        merged = merged[-CACHE_MAX:]
    CACHE_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

# ─────────────────────────────────────────────
# Step 1: RSSフィード収集
# ─────────────────────────────────────────────

def collect_rss(src: Source, processed_urls: set[str]) -> list[dict]:
    feed = feedparser.parse(src.rss)
    if not feed.entries:
        return []

    items = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title:
            continue
        if any(k in title.lower() for k in src.skip_keywords):
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
        body = _strip_html(body)

        published = pub_dt.isoformat() if pub_dt else datetime.now(timezone.utc).isoformat()
        items.append({"url": url, "title": title, "body": body, "published": published})

    return items

# ─────────────────────────────────────────────
# Step 1b: VideoCardz/Neowin — Google News RSS
# ─────────────────────────────────────────────

def collect_via_gnews(src: Source, processed_urls: set[str]) -> list[dict]:
    if not HAS_GNEWS or not src.gnews_rss:
        return []

    feed = feedparser.parse(src.gnews_rss)
    items = []
    for entry in feed.entries[:25]:
        gnews_url = entry.get("link", "")
        if not gnews_url:
            continue

        pub_dt = _parse_published(entry)
        if not _is_within_24h(pub_dt):
            continue

        try:
            result = gnewsdecoder(gnews_url, interval=1)
            real_url = result.get("decoded_url", "")
            if not real_url or real_url in processed_urls:
                continue
        except Exception:
            continue

        title = entry.get("title", "").strip()
        published = pub_dt.isoformat() if pub_dt else datetime.now(timezone.utc).isoformat()
        items.append({"url": real_url, "title": title, "body": "", "published": published})
        time.sleep(0.5)

    return items

# ─────────────────────────────────────────────
# Step 2〜4: フェッチ
# ─────────────────────────────────────────────

def fetch_httpx(url: str) -> Optional[str]:
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code != 200:
                return None
            html = r.text
            for pat in [r"<article[^>]*>(.*?)</article>",
                        r"<main[^>]*>(.*?)</main>"]:
                m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
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
        ctx = await browser.new_context(
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
    """(本文テキスト, 使用手法) を返す。取得失敗時は ("", "failed")"""

    # rss_full: RSSに全文あり
    if src.fetch_method == "rss_full" and len(rss_body) >= MIN_BODY_LEN:
        return rss_body, "rss_full"

    # httpx
    if src.fetch_method in ("httpx", "rss_full"):
        t = fetch_httpx(url)
        if t:
            return t, "httpx"

    # jina
    if src.fetch_method in ("jina", "httpx", "rss_full"):
        t = fetch_jina(url)
        if t:
            return t, "jina"

    # playwright（全手法のfallback）
    t = await fetch_playwright(url, browser)
    if t:
        return t, "playwright"

    return "", "failed"

# ─────────────────────────────────────────────
# 3層重複排除
# ─────────────────────────────────────────────

def dedup_and_limit(articles: list[RawArticle]) -> list[RawArticle]:
    """
    Layer 1: URL完全一致
    Layer 2: タイトルフィンガープリント
    Layer 3: カテゴリ別上限（MUST_CATCHは除外）
    """
    # スコア降順でソート（高品質を優先）
    articles = sorted(articles, key=lambda x: -x.score)

    seen_urls: set[str]   = set()
    seen_fps:  set[str]   = set()
    cat_counts: Counter   = Counter()
    result: list[RawArticle] = []

    for a in articles:
        # Layer 1: URL
        if a.url in seen_urls:
            continue
        # Layer 2: タイトルFP
        fp = _title_fingerprint(a.title)
        if fp in seen_fps:
            continue
        # Layer 3: カテゴリ上限（MUST_CATCHは無条件通過）
        limit = CATEGORY_LIMITS.get(a.category, 3)
        if not a.is_must_catch and cat_counts[a.category] >= limit:
            continue

        seen_urls.add(a.url)
        seen_fps.add(fp)
        cat_counts[a.category] += 1
        result.append(a)

    return result

# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

async def main():
    processed_urls = load_processed_urls()
    print(f"処理済みURLキャッシュ: {len(processed_urls)} 件")

    all_articles: list[RawArticle] = []
    new_urls: set[str] = set()
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
                        url=entry["url"],
                        title=entry["title"],
                        body=body,
                        source_name=_src.name,
                        tier=_src.tier,
                        category=cat,
                        published=entry["published"],
                        fetch_method_used=method,
                    )
                    flag = "🔴 MUST_CATCH" if art.is_must_catch else ("🟡 LEAK" if art.is_leak else "")
                    print(f"    ✅ [{method}] {len(body):,}字 {flag} : {entry['title'][:55]}")
                    return art

            tasks = [process(e) for e in entries]
            results = await asyncio.gather(*tasks)

            for a in results:
                if a:
                    all_articles.append(a)
                    new_urls.add(a.url)

        await browser.close()

    # 重複排除 + カテゴリ上限適用
    deduped = dedup_and_limit(all_articles)
    print(f"\n重複排除・上限適用: {len(all_articles)} → {len(deduped)} 件")

    # JSONLで出力（generate.pyへの受け渡し）
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for a in deduped:
            f.write(json.dumps(asdict(a), ensure_ascii=False) + "\n")

    # 処理済みURLをキャッシュに保存
    save_processed_urls(new_urls)
    print(f"キャッシュ更新: +{len(new_urls)} URL")

    # ── サマリー ──────────────────────────────────
    print("\n" + "=" * 60)
    print("収集サマリー")
    print("=" * 60)
    print(f"{'カテゴリ':<14} {'本数':>5}  記事例")
    print("-" * 60)
    by_cat: dict[str, list[RawArticle]] = defaultdict(list)
    for a in deduped:
        by_cat[a.category].append(a)
    for cat, arts in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        example = arts[0].title[:40] if arts else ""
        print(f"  {cat:<12} {len(arts):>5}本  {example}...")

    print(f"\n合計: {len(deduped)} 件  "
          f"(MUST_CATCH: {sum(1 for a in deduped if a.is_must_catch)}, "
          f"LEAK: {sum(1 for a in deduped if a.is_leak)})")
    print(f"出力: {OUTPUT_PATH}")

    must_catch_arts = [a for a in deduped if a.is_must_catch]
    if must_catch_arts:
        print("\n── MUST_CATCH 記事一覧 ──")
        for a in must_catch_arts:
            print(f"  [{a.source_name}] {a.title[:65]}")


if __name__ == "__main__":
    asyncio.run(main())
