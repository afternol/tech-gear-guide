# -*- coding: utf-8 -*-
"""
Step4: 代替ソース検索（DuckDuckGo）
Step5: Playwright ヘッドレスブラウザ
の2手法をテスト
"""
import sys, io, re, asyncio, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx
from playwright.async_api import async_playwright

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def quality(text: str | None) -> str:
    if not text:
        return "❌ 取得不可"
    l = len(text)
    if l >= 2000:
        return f"✅ 全文 ({l:,}字)"
    if l >= 500:
        return f"⚠️  部分 ({l:,}字)"
    return f"❌ 短すぎ ({l:,}字)"

# =====================
# Step 4: 代替ソース検索
# =====================

# 全滅ソースの記事タイトル（RSSから取得済みのもの）
FAILED_ARTICLES = [
    {
        "source": "9to5Mac",
        "title": "iPhone 18 Pro Max may be thicker, iPhone Ultra dummy unit compared to 17 Pro Max",
        "url": "https://9to5mac.com/2026/04/23/iphone-18-pro-max-may-be-thicker-iphone-ultra-dummy-unit-compared-to-17-pro-max/",
    },
    {
        "source": "Windows Central",
        "title": "Devs behind canceled Xbox game are hiring for an unannounced AAA open-world title",
        "url": "https://www.windowscentral.com/gaming/devs-behind-canceled-xbox-game-are-hiring-for-an-unannounced-aaa-open-world-title",
    },
    {
        "source": "Tom's Hardware",
        "title": "New 3D device computes using living brain cells bioelectronic device",
        "url": "https://www.tomshardware.com/tech-industry/big-tech/new-3d-device-computes-using-living-brain-cells-bioelectronic-device-uses-3d-electronic-mesh-design-paired-with-living-tissue",
    },
]

# 取得可能なソースドメイン（フォールバック検索対象）
FETCHABLE_DOMAINS = [
    "macrumors.com",
    "androidauthority.com",
    "gsmarena.com",
    "engadget.com",
    "xda-developers.com",
    "notebookcheck.net",
    "arstechnica.com",
]

def search_alternative_source(title: str) -> list[str]:
    """DuckDuckGo HTML 検索で代替ソースURLを取得"""
    # タイトルのキーワードを抽出（最初の8単語）
    keywords = " ".join(title.split()[:8])
    query = keywords
    search_url = f"https://html.duckduckgo.com/html/?q={httpx.URL(f'?q={query}').params['q']}"

    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": keywords},
            )
            if resp.status_code != 200:
                return []
            html = resp.text
            # href から結果URLを抽出
            urls = re.findall(r'href="(https?://[^"]+)"', html)
            # 取得可能ドメインに絞る
            results = []
            for url in urls:
                for domain in FETCHABLE_DOMAINS:
                    if domain in url and url not in results:
                        results.append(url)
            return results[:3]
    except Exception as e:
        print(f"    検索エラー: {e}")
        return []

def direct_fetch_text(url: str) -> str | None:
    """httpx で直接フェッチして本文テキストを抽出"""
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            html = resp.text
            for pattern in [
                r"<article[^>]*>(.*?)</article>",
                r"<main[^>]*>(.*?)</main>",
                r"<body[^>]*>(.*?)</body>",
            ]:
                m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                if m:
                    text = strip_html(m.group(1))
                    if len(text) > 500:
                        return text
            return None
    except Exception:
        return None

# =====================
# Step 5: Playwright
# =====================

async def playwright_fetch(url: str) -> str | None:
    """Playwright ヘッドレスブラウザで全文取得"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)  # JS描画待ち

            # 本文候補セレクタを順番に試す
            for selector in ["article", "main", ".article-body", ".post-content", ".entry-content", "body"]:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.inner_text()
                        text = re.sub(r"\s+", " ", text).strip()
                        if len(text) > 500:
                            await browser.close()
                            return text
                except Exception:
                    continue

            await browser.close()
            return None
    except Exception as e:
        return None

# =====================
# メインテスト
# =====================

async def main():
    print("=" * 70)
    print("Step 4: 代替ソース検索テスト")
    print("=" * 70)

    for art in FAILED_ARTICLES:
        print(f"\n[元ソース: {art['source']}]")
        print(f"  タイトル: {art['title'][:60]}...")

        alt_urls = search_alternative_source(art["title"])
        if not alt_urls:
            print("  → 代替URLなし")
            continue

        for alt_url in alt_urls:
            print(f"  代替URL: {alt_url[:70]}")
            text = direct_fetch_text(alt_url)
            print(f"  結果   : {quality(text)}")
            if text and len(text) > 500:
                print(f"  冒頭   : {text[:150]}...")
                break
        time.sleep(1)

    print("\n" + "=" * 70)
    print("Step 5: Playwright テスト（全滅ソース直接フェッチ）")
    print("=" * 70)

    pw_targets = [
        ("9to5Mac",         "https://9to5mac.com/2026/04/23/iphone-18-pro-max-may-be-thicker-iphone-ultra-dummy-unit-compared-to-17-pro-max/"),
        ("9to5Google",      "https://9to5google.com/2026/04/24/google-home-isnt-killing-automations-but-phone-related-actions-are-going-away/"),
        ("Windows Central", "https://www.windowscentral.com/gaming/devs-behind-canceled-xbox-game-are-hiring-for-an-unannounced-aaa-open-world-title"),
        ("Tom's Hardware",  "https://www.tomshardware.com/tech-industry/big-tech/new-3d-device-computes-using-living-brain-cells-bioelectronic-device-uses-3d-electronic-mesh-design-paired-with-living-tissue"),
        ("TechRadar",       "https://www.techradar.com/best/best-gaming-laptops"),
    ]

    for name, url in pw_targets:
        print(f"\n[{name}]")
        print(f"  URL: {url[:70]}")
        text = await playwright_fetch(url)
        print(f"  Playwright: {quality(text)}")
        if text and len(text) > 500:
            print(f"  冒頭: {text[:150]}...")

asyncio.run(main())
