# -*- coding: utf-8 -*-
"""
Wccftech / VideoCardz / Neowin 突破テスト
playwright-stealth + domcontentloaded + 長めタイムアウト + Google検索代替
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
    return re.sub(r"\s+", " ", text).strip()

def quality(text, label=""):
    if not text:
        return "❌ 取得不可"
    l = len(text)
    if l >= 2000: return f"✅ 全文 ({l:,}字)"
    if l >= 500:  return f"⚠️  部分 ({l:,}字)"
    return f"❌ 短すぎ ({l:,}字)"

# ---- stealth適用ヘルパー ----
def apply_stealth(page):
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except Exception:
        pass

async def apply_stealth_async(page):
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except Exception:
        pass

# ---- Playwrightフェッチ（stealth + domcontentloaded） ----
async def pw_fetch_stealth(url: str, browser, timeout_ms: int = 40000) -> tuple[str | None, str]:
    """stealthモード + domcontentloaded で全文取得を試みる"""
    try:
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = await ctx.new_page()
        await apply_stealth_async(page)

        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(3000)

        # タイトル確認（Cloudflare challenge判定）
        title = await page.title()
        if "just a moment" in title.lower() or "cloudflare" in title.lower():
            # Cloudflare challenge: さらに待つ
            await page.wait_for_timeout(5000)
            title = await page.title()

        content = await page.content()
        text_body = None

        # セレクタ順に試す
        for sel in [
            "article",
            ".article-body", ".article__body", ".article-content",
            ".post-body", ".post-content", ".entry-content",
            ".content-body", ".story-body",
            "[class*='article']", "[class*='content']",
            "main",
        ]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    t = await el.inner_text()
                    t = re.sub(r"\s+", " ", t).strip()
                    if len(t) > 800:
                        text_body = t
                        break
            except Exception:
                continue

        if not text_body:
            # body全体fallback
            try:
                t = await page.inner_text("body")
                t = re.sub(r"\s+", " ", t).strip()
                if len(t) > 500:
                    text_body = t
            except Exception:
                pass

        await ctx.close()
        return text_body, title

    except Exception as e:
        return None, str(e)

# ---- Google News 経由でURLを取得 ----
def google_news_search(query: str, site: str) -> list[str]:
    """Google News検索でsite:指定のURLを取得"""
    try:
        search_q = f"site:{site} {query}"
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(
                "https://news.google.com/search",
                params={"q": search_q, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            )
            if r.status_code != 200:
                return []
            # Google News のリダイレクトURLからオリジナルURLを抽出
            urls = re.findall(r'href="(https?://' + re.escape(site) + r'[^"]+)"', r.text)
            return list(dict.fromkeys(urls))[:3]
    except Exception:
        return []

def duckduckgo_search(query: str, site: str) -> list[str]:
    """DuckDuckGo検索でsite:指定のURLを取得"""
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"site:{site} {query}"},
            )
            if r.status_code != 200:
                return []
            urls = re.findall(r'href="(https?://' + re.escape(site) + r'[^"]+)"', r.text)
            return list(dict.fromkeys(urls))[:3]
    except Exception:
        return []

async def main():
    print("=" * 70)
    print("Wccftech / VideoCardz / Neowin 全文取得テスト")
    print("=" * 70)

    # ---- 各サイトの記事URLを事前取得 ----
    # Wccftech: RSSから取得済み
    WCCFTECH_ARTICLE = "https://wccftech.com/ddr5-ram-prices-finally-crack-in-japan-as-64-gb-kits-dip-below-489-for-first-time-in-four-months/"

    # VideoCardz / Neowin: Google/DDG検索で記事URLを探す
    print("\n[VideoCardz] 記事URL検索中...")
    vc_urls = (
        google_news_search("GPU RTX", "videocardz.com") or
        duckduckgo_search("GPU RTX leak", "videocardz.com")
    )
    VC_ARTICLE = vc_urls[0] if vc_urls else None
    print(f"  → {VC_ARTICLE}")

    print("\n[Neowin] 記事URL検索中...")
    nw_urls = (
        google_news_search("Windows Microsoft", "www.neowin.net") or
        duckduckgo_search("Windows Microsoft", "neowin.net")
    )
    NW_ARTICLE = nw_urls[0] if nw_urls else None
    print(f"  → {NW_ARTICLE}")

    # URLが見つからない場合: 既知パターンからhttpxで直接取得
    if not VC_ARTICLE:
        vc_test_urls = [
            "https://videocardz.com/newz/",
        ]
        for u in vc_test_urls:
            try:
                with httpx.Client(headers=BROWSER_HEADERS, timeout=10, follow_redirects=True) as c:
                    r = c.get(u)
                    if r.status_code == 200:
                        links = re.findall(r'href="(https://videocardz\.com/newz/[^"]+)"', r.text)
                        if links:
                            VC_ARTICLE = links[0]
                            print(f"  [VideoCardz] httpxトップページから取得: {VC_ARTICLE}")
                            break
            except Exception:
                pass

    TARGETS = [
        ("Wccftech",   WCCFTECH_ARTICLE),
        ("VideoCardz", VC_ARTICLE),
        ("Neowin",     NW_ARTICLE),
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        results = []

        for name, url in TARGETS:
            print(f"\n{'='*60}")
            print(f"[{name}]")
            if not url:
                print("  記事URL: 取得できず → スキップ")
                results.append((name, "❌", "❌", "❌", "❌ URLなし"))
                continue
            print(f"  URL: {url[:80]}")

            # Step2: httpx
            httpx_text = None
            try:
                with httpx.Client(headers=BROWSER_HEADERS, timeout=15, follow_redirects=True) as c:
                    r = c.get(url)
                    print(f"  httpx status: {r.status_code}")
                    if r.status_code == 200:
                        html = r.text
                        for pat in [r"<article[^>]*>(.*?)</article>",
                                    r"<main[^>]*>(.*?)</main>"]:
                            m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
                            if m:
                                t = strip_html(m.group(1))
                                if len(t) > 500:
                                    httpx_text = t
                                    break
            except Exception as e:
                print(f"  httpxエラー: {e}")
            print(f"  Step2 httpx     : {quality(httpx_text)}")

            # Step3: Jina
            jina_text = None
            if not httpx_text:
                try:
                    with httpx.Client(timeout=20, follow_redirects=True) as c:
                        r = c.get(f"https://r.jina.ai/{url}")
                        if r.status_code == 200 and len(r.text) > 200:
                            jina_text = r.text.strip()
                except Exception:
                    pass
            print(f"  Step3 Jina      : {quality(jina_text)}")

            # Step4: Playwright stealth
            best_so_far = httpx_text or jina_text
            pw_text = None
            if not best_so_far or len(best_so_far) < 1000:
                print(f"  Step4 Playwright stealth: 実行中...")
                pw_text, page_title = await pw_fetch_stealth(url, browser, timeout_ms=45000)
                print(f"  ページタイトル : {page_title[:60]}")
                print(f"  Step4 Playwright: {quality(pw_text)}")
            else:
                print(f"  Step4 Playwright: スキップ")

            best = pw_text or httpx_text or jina_text
            best_q = quality(best)
            print(f"  → 最良結果     : {best_q}")
            if best and len(best) > 200:
                print(f"  冒頭           : {best[:200]}...")

            results.append((name, quality(httpx_text), quality(jina_text), quality(pw_text), best_q))

        await browser.close()

    print("\n" + "=" * 70)
    print("サマリー")
    print("=" * 70)
    print(f"{'ソース':<14} {'httpx':<20} {'Jina':<20} {'Playwright':<20} {'最良'}")
    print("-" * 80)
    for r in results:
        print(f"{r[0]:<14} {r[1]:<20} {r[2]:<20} {r[3]:<20} {r[4]}")

asyncio.run(main())
