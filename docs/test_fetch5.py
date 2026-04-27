# -*- coding: utf-8 -*-
"""VideoCardz / Neowin — 実URLで全手法テスト"""
import sys, io, re, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx
from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

def q(text, label=""):
    if not text: return "❌ 取得不可"
    l = len(text)
    if l >= 2000: return f"✅ 全文 ({l:,}字)"
    if l >= 500:  return f"⚠️  部分 ({l:,}字)"
    return f"❌ 短すぎ ({l:,}字)"

def httpx_fetch(url):
    try:
        with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code != 200:
                return None, r.status_code
            html = r.text
            for pat in [r"<article[^>]*>(.*?)</article>",
                        r"<main[^>]*>(.*?)</main>"]:
                m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
                if m:
                    t = strip(m.group(1))
                    if len(t) > 500: return t, 200
            return None, 200
    except Exception as e:
        return None, str(e)

def jina_fetch(url):
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            r = c.get(f"https://r.jina.ai/{url}")
            return (r.text.strip() if r.status_code == 200 and len(r.text) > 200 else None), r.status_code
    except Exception as e:
        return None, str(e)

async def pw_fetch(url, browser, timeout_ms=40000):
    try:
        ctx = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()
        if HAS_STEALTH:
            await stealth_async(page)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(3000)
        title = await page.title()
        # Cloudflare challenge検出
        if any(k in title.lower() for k in ["just a moment", "cloudflare", "security check", "captcha"]):
            print(f"    Cloudflare検出: '{title}' → 追加待機5秒")
            await page.wait_for_timeout(5000)
            title = await page.title()

        for sel in ["article", ".article-body", ".article__body", ".post-content",
                    ".entry-content", ".content-body", ".article-content",
                    "[class*='article']", "main"]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    t = re.sub(r"\s+", " ", await el.inner_text()).strip()
                    if len(t) > 500:
                        await ctx.close()
                        return t, title
            except Exception:
                continue
        # body fallback
        try:
            t = re.sub(r"\s+", " ", await page.inner_text("body")).strip()
            await ctx.close()
            return (t if len(t) > 500 else None), title
        except Exception:
            pass
        await ctx.close()
        return None, title
    except Exception as e:
        return None, str(e)

TARGETS = [
    ("VideoCardz", "https://videocardz.com/newz/amd-expo-1-2-now-available-adds-partial-cudimm-support-and-three-new-chinese-memory-vendors"),
    ("VideoCardz2","https://videocardz.com/newz/intel-says-software-optimization-can-hide-up-to-30-gaming-cpu-performance"),
    ("Neowin",     "https://www.neowin.net/news/microsoft-windows-11-kb5083769-kb5082052-updates-causing-remote-desktop-issues/"),
    ("Neowin2",    "https://www.neowin.net/news/openai-launches-autonomous-workspace-agents-in-chatgpt/"),
]

async def main():
    print("=" * 70)
    print("VideoCardz / Neowin 全文取得テスト（実URL使用）")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for name, url in TARGETS:
            print(f"\n[{name}]")
            print(f"  URL: {url[:75]}")

            # httpx
            h_text, h_code = httpx_fetch(url)
            print(f"  httpx (status={h_code}): {q(h_text)}")

            # Jina
            j_text, j_code = jina_fetch(url)
            print(f"  Jina  (status={j_code}): {q(j_text)}")

            # Playwright
            best = h_text or j_text
            if not best or len(best) < 1000:
                pw_text, pg_title = await pw_fetch(url, browser)
                print(f"  Playwright page_title: '{pg_title[:50]}'")
                print(f"  Playwright: {q(pw_text)}")
            else:
                pw_text = None
                print(f"  Playwright: スキップ（httpx/Jinaで十分）")

            best = h_text or pw_text or j_text
            print(f"  → 最良: {q(best)}")
            if best and len(best) > 100:
                print(f"  冒頭 : {best[:180]}...")

        await browser.close()

asyncio.run(main())
