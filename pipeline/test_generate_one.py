# -*- coding: utf-8 -*-
"""1記事だけ生成してSupabaseに投稿するテスト"""
import asyncio, json, os, sys

from dotenv import load_dotenv
load_dotenv()

from generate import (
    RawArticle, build_a_type_prompt, generate_article,
    parse_meta, extract_body
)
from publish import insert_article, ArticleRow
import anthropic
from datetime import datetime, timezone

SAMPLE = RawArticle(
    url="https://www.macrumors.com/2026/04/27/iphone-17-test/",
    title="iPhone 17 Air to Feature Thinnest iPhone Design Yet at 5.5mm",
    body=(
        "Apple's upcoming iPhone 17 Air is expected to feature the thinnest iPhone design "
        "in the company's history, measuring just 5.5mm at its thinnest point. "
        "The device will reportedly use a new A19 chip built on TSMC's 3nm process, "
        "delivering approximately 20% better performance than the A18. "
        "The camera system will be upgraded with a 48MP main sensor and improved Night Mode. "
        "Battery capacity will be 3,000mAh, slightly smaller than iPhone 16, "
        "but Apple claims efficiency gains will maintain all-day battery life. "
        "The phone is expected to launch in September 2026 starting at $799. "
        "It will come in four colors: titanium, pink, sky blue, and desert gold."
    ),
    source_name="MacRumors",
    tier=2,
    category="smartphone",
    published="2026-04-27T08:00:00+00:00",
    fetch_method_used="rss_full",
)

async def main():
    print("=== テスト記事生成 ===")
    client = anthropic.AsyncAnthropic()
    sem    = asyncio.Semaphore(1)
    prompt = build_a_type_prompt(SAMPLE)

    print(f"プロンプト長: {len(prompt)} 文字")
    print("生成中...")

    result = await generate_article(client, prompt, "A型速報", SAMPLE, sem)
    if not result:
        print("生成失敗")
        return

    print(f"\n✅ 生成完了")
    print(f"  タイトル: {result.title}")
    print(f"  スラッグ: {result.slug}")
    print(f"  本文長:   {len(result.body)} 文字")
    print(f"\n── 本文冒頭 ──")
    print(result.body[:400])
    print("...")

    # Supabaseに投稿
    print("\n── Supabase投稿 ──")
    row = ArticleRow(
        title=result.title,
        slug=result.slug,
        body=result.body,
        category=result.category,
        tags=result.tags,
        article_type=result.article_type,
        source_reliability=result.source_reliability,
        sources=result.sources,
        featured_image_url="",
        featured_image_source="",
        featured_image_credit="",
        seo_description=result.seo_description,
        published_at=result.published_at,
        is_must_catch=result.is_must_catch,
        is_leak=result.is_leak,
    )
    ok, err = insert_article(row)
    if ok:
        print(f"✅ Supabase投稿成功: /articles/{result.slug}")
    else:
        print(f"❌ 投稿失敗: {err}")

asyncio.run(main())
