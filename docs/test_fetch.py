# -*- coding: utf-8 -*-
"""
DeviceBrief 全文取得手法テスト
各ソースに対して Step1(RSS) → Step2(httpx直接) → Step3(Jina) の順で試す
"""
import sys, io, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import feedparser
import httpx

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

BOT_HEADERS = {
    "User-Agent": "DeviceBrief/1.0 (+https://devicebrief.com)",
}

# テスト対象ソース: (name, rss_url)
SOURCES = [
    ("9to5Mac",           "https://9to5mac.com/feed/"),
    ("9to5Google",        "https://9to5google.com/feed/"),
    ("Android Authority", "https://www.androidauthority.com/feed/"),
    ("MacRumors",         "https://feeds.macrumors.com/MacRumors-Front"),
    ("GSMArena",          "https://www.gsmarena.com/rss-news-reviews.php3"),
    ("XDA Developers",    "https://www.xda-developers.com/feed/"),
    ("Windows Central",   "https://www.windowscentral.com/rss"),
    ("Tom's Hardware",    "http://www.tomshardware.com/feeds.xml"),
    ("NotebookCheck",     "https://www.notebookcheck.net/News.152.100.html"),
    ("Engadget",          "https://www.engadget.com/rss.xml"),
    ("TechRadar",         "https://www.techradar.com/feeds/articletype/news"),
    ("Wccftech",          "https://wccftech.com/feed/"),
    ("VideoCardz",        "https://videocardz.com/feed"),
    ("Neowin",            "https://www.neowin.net/news/full-rss/"),
    ("Ars Technica",      "https://feeds.arstechnica.com/arstechnica/technology-lab"),
]

def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def rss_full_text(rss_url: str) -> tuple[str | None, str | None]:
    """RSS から最初の記事の全文とURLを取得"""
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            return None, None
        entry = feed.entries[0]
        url = entry.get("link", "")
        # content:encoded → summary の順で試す
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        if not content:
            content = entry.get("summary", "")
        text = strip_html(content)
        return text if len(text) > 100 else None, url
    except Exception as e:
        return None, None

def direct_fetch(url: str, use_browser_ua: bool = True) -> str | None:
    """httpx で直接フェッチして本文テキストを抽出"""
    headers = BROWSER_HEADERS if use_browser_ua else BOT_HEADERS
    try:
        with httpx.Client(headers=headers, timeout=15, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            html = resp.text
            # <article> タグ内を優先
            m = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
            if m:
                return strip_html(m.group(1))
            # <main> タグ
            m = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL | re.IGNORECASE)
            if m:
                return strip_html(m.group(1))
            # body全体 fallback
            m = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
            if m:
                text = strip_html(m.group(1))
                return text if len(text) > 200 else None
            return None
    except Exception as e:
        return None

def jina_fetch(url: str) -> str | None:
    """Jina Reader API で全文取得"""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(jina_url)
            if resp.status_code == 200:
                text = resp.text.strip()
                return text if len(text) > 200 else None
            return None
    except Exception as e:
        return None

def quality(text: str | None) -> str:
    if text is None:
        return "❌ 取得不可"
    l = len(text)
    if l >= 2000:
        return f"✅ 全文 ({l:,}字)"
    if l >= 500:
        return f"⚠️  部分 ({l:,}字)"
    return f"❌ 短すぎ ({l:,}字)"

print("=" * 70)
print("DeviceBrief 全文取得テスト")
print("=" * 70)

results = []

for name, rss_url in SOURCES:
    print(f"\n[{name}]")
    article_url = None

    # --- Step 1: RSS ---
    rss_text, article_url = rss_full_text(rss_url)
    rss_q = quality(rss_text)
    print(f"  Step1 RSS       : {rss_q}")
    if article_url:
        print(f"  記事URL         : {article_url[:80]}")

    # --- Step 2: httpx 直接 (ブラウザUA) ---
    direct_text = None
    if article_url:
        direct_text = direct_fetch(article_url, use_browser_ua=True)
    direct_q = quality(direct_text)
    print(f"  Step2 httpx直接 : {direct_q}")

    # --- Step 3: Jina Reader ---
    jina_text = None
    if article_url and (direct_text is None or len(direct_text) < 500):
        time.sleep(1)  # Jina へのリクエスト間隔
        jina_text = jina_fetch(article_url)
    jina_q = quality(jina_text)
    if article_url and (direct_text is None or len(direct_text) < 500):
        print(f"  Step3 Jina      : {jina_q}")
    else:
        print(f"  Step3 Jina      : スキップ（Step2で十分）")

    # 最良の結果
    best = direct_text or jina_text or rss_text
    best_q = quality(best)
    print(f"  → 最良結果      : {best_q}")

    results.append({
        "name": name,
        "rss": rss_q,
        "direct": direct_q,
        "jina": jina_q,
        "best": best_q,
    })
    time.sleep(0.5)

print("\n" + "=" * 70)
print("サマリー")
print("=" * 70)
print(f"{'ソース':<22} {'RSS':<20} {'httpx直接':<20} {'最良'}")
print("-" * 70)
for r in results:
    print(f"{r['name']:<22} {r['rss']:<20} {r['direct']:<20} {r['best']}")
