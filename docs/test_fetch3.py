# -*- coding: utf-8 -*-
"""
TechRadar / Wccftech / VideoCardz / Neowin 全文取得テスト
RSS・httpx・Jina・Playwrightの全手法を試す
"""
import sys, io, re, asyncio, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import feedparser, httpx
from playwright.async_api import async_playwright

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

def quality(text: str | None, label: str = "") -> str:
    if not text:
        return "❌ 取得不可"
    l = len(text)
    mark = "✅ 全文" if l >= 2000 else ("⚠️  部分" if l >= 500 else "❌ 短すぎ")
    return f"{mark} ({l:,}字)"

def rss_get(feed_url: str, skip_keywords: list[str] = []) -> tuple[str | None, str | None]:
    """RSSから記事URLと本文テキストを返す（スキップキーワードを除外）"""
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.get("title", "").lower()
            if any(k in title for k in skip_keywords):
                continue
            url = entry.get("link", "")
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            if not content:
                content = entry.get("summary", "")
            text = strip_html(content)
            return (text if len(text) > 100 else None), url
        return None, None
    except Exception:
        return None, None

def httpx_fetch(url: str) -> str | None:
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code != 200:
                return None
            html = r.text
            for pat in [r"<article[^>]*>(.*?)</article>",
                        r"<main[^>]*>(.*?)</main>",
                        r"<body[^>]*>(.*?)</body>"]:
                m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
                if m:
                    t = strip_html(m.group(1))
                    if len(t) > 500:
                        return t
        return None
    except Exception:
        return None

def jina_fetch(url: str) -> str | None:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            r = c.get(f"https://r.jina.ai/{url}")
            if r.status_code == 200 and len(r.text) > 200:
                return r.text.strip()
        return None
    except Exception:
        return None

async def pw_fetch(url: str, browser) -> str | None:
    """Playwrightで全文取得"""
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        # Cloudflare challenge等をある程度回避するためdomcontentloadedでなくloadを待つ
        await page.goto(url, wait_until="load", timeout=25000)
        await page.wait_for_timeout(2500)

        for sel in ["article", ".article-body", ".article__body",
                    ".post-content", ".entry-content", ".content-body",
                    ".article-content", "main", "body"]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.inner_text()
                    text = re.sub(r"\s+", " ", text).strip()
                    if len(text) > 500:
                        await context.close()
                        return text
            except Exception:
                continue
        await context.close()
        return None
    except Exception as e:
        return None

async def pw_get_article_url(homepage: str, browser, domain: str) -> str | None:
    """Playwrightでトップページから最初のニュース記事URLを取得"""
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(homepage, wait_until="load", timeout=25000)
        await page.wait_for_timeout(2000)
        # href から同ドメインの記事URLを探す
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.href)"
        )
        skip = ["category", "tag", "author", "page", "search", "about",
                "contact", "privacy", "advertise", "#", "javascript"]
        news_links = [
            l for l in links
            if domain in l
            and not any(s in l.lower() for s in skip)
            and len(l) > len(homepage) + 10
        ]
        await context.close()
        # 重複除去して最初の1件
        seen = set()
        for l in news_links:
            if l not in seen:
                seen.add(l)
                return l
        return None
    except Exception as e:
        return None


async def main():
    # -------- 事前情報 --------
    # TechRadar: RSSから取得済みの有効記事URL
    TECHRADAR_URL = "https://www.techradar.com/computing/laptops/new-windows-11-laptop-looks-like-a-true-macbook-neo-rival-that-should-worry-apple"
    TECHRADAR_RSS = "https://www.techradar.com/feeds/articletype/news"
    WCCFTECH_URL  = "https://wccftech.com/ddr5-ram-prices-finally-crack-in-japan-as-64-gb-kits-dip-below-489-for-first-time-in-four-months/"
    WCCFTECH_RSS  = "https://wccftech.com/feed/"

    # VideoCardz・Neowinはホームページから記事URLをPlaywrightで取得
    VC_HOME    = "https://videocardz.com/"
    NEOWIN_HOME = "https://www.neowin.net/"

    print("=" * 70)
    print("全手法テスト: TechRadar / Wccftech / VideoCardz / Neowin")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ---- VideoCardz: まずPlaywrightで記事URLを取得 ----
        print("\n[VideoCardz] ホームページから記事URL取得中...")
        vc_url = await pw_get_article_url(VC_HOME, browser, "videocardz.com")
        print(f"  記事URL: {vc_url}")

        # ---- Neowin: 同上 ----
        print("\n[Neowin] ホームページから記事URL取得中...")
        nw_url = await pw_get_article_url(NEOWIN_HOME, browser, "neowin.net")
        print(f"  記事URL: {nw_url}")

        TARGETS = [
            {
                "name": "TechRadar",
                "rss": TECHRADAR_RSS,
                "rss_skip": ["quordle","nyt","wordle","strands","connections","crossword","sudoku"],
                "url": TECHRADAR_URL,
            },
            {
                "name": "Wccftech",
                "rss": WCCFTECH_RSS,
                "rss_skip": [],
                "url": WCCFTECH_URL,
            },
            {
                "name": "VideoCardz",
                "rss": None,
                "rss_skip": [],
                "url": vc_url,
            },
            {
                "name": "Neowin",
                "rss": None,
                "rss_skip": [],
                "url": nw_url,
            },
        ]

        results = []

        for t in TARGETS:
            name = t["name"]
            url  = t["url"]
            print(f"\n{'='*60}")
            print(f"[{name}]")
            print(f"  テスト記事: {str(url)[:80]}")

            # Step 1: RSS
            rss_text = None
            if t["rss"]:
                rss_text, _ = rss_get(t["rss"], t["rss_skip"])
            rss_q = quality(rss_text)
            print(f"  Step1 RSS       : {rss_q}")

            if not url:
                print("  → 記事URL取得失敗・スキップ")
                results.append({"name": name, "rss": rss_q, "httpx": "—", "jina": "—", "pw": "—", "best": "❌"})
                continue

            # Step 2: httpx
            httpx_text = httpx_fetch(url)
            httpx_q = quality(httpx_text)
            print(f"  Step2 httpx     : {httpx_q}")

            # Step 3: Jina
            jina_text = None
            if not httpx_text or len(httpx_text) < 1000:
                jina_text = jina_fetch(url)
                jina_q = quality(jina_text)
                print(f"  Step3 Jina      : {jina_q}")
            else:
                jina_q = "スキップ"
                print(f"  Step3 Jina      : スキップ")

            # Step 4: Playwright
            pw_text = None
            best_so_far = httpx_text or jina_text or rss_text
            if not best_so_far or len(best_so_far) < 1000:
                print(f"  Step4 Playwright: 実行中...")
                pw_text = await pw_fetch(url, browser)
                pw_q = quality(pw_text)
                print(f"  Step4 Playwright: {pw_q}")
            else:
                pw_q = "スキップ"
                print(f"  Step4 Playwright: スキップ")

            best = pw_text or httpx_text or jina_text or rss_text
            best_q = quality(best)
            print(f"  → 最良結果      : {best_q}")
            if best and len(best) > 200:
                # noiseを除いた冒頭を表示
                preview = best[:200].replace("\n", " ")
                print(f"  冒頭プレビュー  : {preview}...")

            results.append({
                "name": name, "rss": rss_q, "httpx": httpx_q,
                "jina": jina_q, "pw": pw_q, "best": best_q,
            })

        await browser.close()

    print("\n" + "=" * 70)
    print("サマリー")
    print("=" * 70)
    print(f"{'ソース':<16} {'RSS':<18} {'httpx':<18} {'Jina':<18} {'Playwright':<18} {'最良'}")
    print("-" * 100)
    for r in results:
        print(f"{r['name']:<16} {r['rss']:<18} {r['httpx']:<18} {r['jina']:<18} {r['pw']:<18} {r['best']}")

asyncio.run(main())
