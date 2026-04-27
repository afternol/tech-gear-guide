# -*- coding: utf-8 -*-
"""
Tech Gear Guide — correct.py
audit_report.jsonl の WARN/FAIL 記事を Claude API で自動修正し
generated_articles.jsonl を上書き更新する。
修正後も FAIL 判定が残る記事は除外して publish.py に渡す。
"""

import asyncio
import json
import re
import sys
import io
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

INPUT_PATH  = Path("generated_articles.jsonl")
REPORT_PATH = Path("audit_report.jsonl")
SOURCE_PATH = Path("collected_articles.jsonl")

MODEL        = "claude-sonnet-4-6"
MAX_PARALLEL = 3

MIN_BODY_LEN = 1200

# ─────────────────────────────────────────────
# プロンプト
# ─────────────────────────────────────────────

_SYSTEM = """\
あなたはTech Gear Guideの編集長です。
記事の事実確認と修正を専門としています。
ソース記事の情報のみを根拠に、指摘された問題点を修正してください。
出力は必ず指定のMETAフォーマットで行ってください。
"""

_CORRECT_PROMPT = """\
以下の記事に問題が発見されました。ソース記事の情報を参照して修正版を出力してください。

【発見された問題】
{issues}

【ソース記事（正しい情報の根拠）】
{source_body}

【修正対象記事】
---META---
title: {title}
slug: {slug}
category: {category}
tags: [{tags}]
article_type: {article_type}
seo_description: {seo_description}
---END_META---

{body}

【修正指示】
- 問題箇所を修正し、同じ出力フォーマット（---META---〜---END_META---＋本文）で出力する
- slug は絶対に変更しない
- ソースにない情報は追加しない
- ソースにある情報は削除しない（必要な事実を残す）
- です・ます調を維持する
- 本文は最低 {min_len} 文字以上
- 年号の誤り（例: 2025年と書かれているが正しくは2026年）は特に注意して修正する
- 「X/5と評価」「★★★☆☆」などの内部スコア表現は削除する
- ソース記事にない別製品・別トピックへの言及を削除する
"""

# ─────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────

def load_source_map() -> dict[str, str]:
    if not SOURCE_PATH.exists():
        return {}
    result: dict[str, str] = {}
    with open(SOURCE_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                result[d.get("url", "")] = d.get("body", "")
    return result

def parse_meta(text: str) -> dict:
    meta: dict[str, str] = {}
    m = re.search(r"---META---(.*?)---END_META---", text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta

def extract_body(text: str) -> str:
    return re.sub(r"---META---.*?---END_META---\n?", "", text, flags=re.DOTALL).strip()

def parse_tags(tags_str: str) -> list[str]:
    return [t.strip().strip("[]") for t in tags_str.split(",") if t.strip()]

def is_still_fail(body: str, title: str, slug: str) -> tuple[bool, list[str]]:
    """修正後の基本チェック。致命的問題のみFAILとする"""
    fails = []
    if len(body) < MIN_BODY_LEN:
        fails.append(f"本文が短すぎます（{len(body)}文字）")
    if not title:
        fails.append("タイトルがありません")
    if not slug or not re.match(r'^[a-z0-9\-]+$', slug):
        fails.append(f"スラッグが不正: {slug}")
    return bool(fails), fails

# ─────────────────────────────────────────────
# 修正処理
# ─────────────────────────────────────────────

async def correct_one(
    client: anthropic.AsyncAnthropic,
    article: dict,
    report: dict,
    source_map: dict,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        slug   = article.get("slug", "")
        status = report.get("status", "PASS")

        # PASS記事は修正不要
        if status == "PASS":
            return article

        all_issues = report.get("issues", []) + report.get("warnings", [])
        if not all_issues:
            return article

        # ソース本文を取得
        source_urls   = [s.get("url", "") for s in article.get("sources", [])]
        source_bodies = [source_map[u] for u in source_urls if u in source_map]

        if not source_bodies:
            print(f"  ⚠️  ソースなし（修正スキップ）: {slug}")
            article["_correction_skipped"] = True
            return article

        # 修正プロンプト作成
        tags_str = ", ".join(article.get("tags", []))
        prompt   = _CORRECT_PROMPT.format(
            issues="\n".join(f"- {i}" for i in all_issues),
            source_body=source_bodies[0][:3500],
            title=article.get("title", ""),
            slug=slug,
            category=article.get("category", ""),
            tags=tags_str,
            article_type=article.get("article_type", "A型速報"),
            seo_description=article.get("seo_description", ""),
            body=article.get("body", "")[:4000],
            min_len=MIN_BODY_LEN,
        )

        try:
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            meta = parse_meta(text)
            body = extract_body(text)

            if not meta.get("title") or len(body) < 800:
                print(f"  ⚠️  修正出力が不十分（本文{len(body)}字）: {slug}")
                article["_correction_failed"] = True
                return article

            # slug は変更させない
            corrected = dict(article)
            corrected["body"]            = body
            corrected["title"]           = meta.get("title", article["title"])
            corrected["seo_description"] = meta.get("seo_description", article.get("seo_description", ""))
            if meta.get("tags"):
                corrected["tags"] = parse_tags(meta["tags"])
            corrected["_corrected"]    = True
            corrected["_corrected_at"] = datetime.now(timezone.utc).isoformat()

            print(f"  ✅ 修正完了 [{status}→修正済]: {slug}")
            return corrected

        except Exception as e:
            print(f"  ❌ 修正エラー（{slug}）: {e}")
            article["_correction_failed"] = True
            return article

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

async def main():
    if not INPUT_PATH.exists():
        print(f"生成記事が見つかりません: {INPUT_PATH}")
        return
    if not REPORT_PATH.exists():
        print(f"監査レポートが見つかりません: {REPORT_PATH}（audit.py を先に実行してください）")
        return

    articles: list[dict] = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                articles.append(json.loads(line))

    reports: dict[str, dict] = {}
    with open(REPORT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                reports[r["slug"]] = r

    source_map = load_source_map()
    print(f"ソース: {len(source_map)} 件ロード")

    need_correction = [
        a for a in articles
        if reports.get(a.get("slug", ""), {}).get("status") in ("WARN", "FAIL")
    ]
    pass_articles = [
        a for a in articles
        if reports.get(a.get("slug", ""), {}).get("status") == "PASS"
    ]

    print(f"修正対象: {len(need_correction)} 件 / PASS（修正不要）: {len(pass_articles)} 件")

    if not need_correction:
        print("修正対象なし。publish.py へ渡します。")
        return

    client = anthropic.AsyncAnthropic()
    sem    = asyncio.Semaphore(MAX_PARALLEL)
    tasks  = [
        correct_one(client, a, reports.get(a.get("slug", ""), {}), source_map, sem)
        for a in need_correction
    ]
    corrected_list = list(await asyncio.gather(*tasks))

    # 修正後の基本チェック → それでもFAILなら除外
    final_articles: list[dict] = list(pass_articles)
    excluded = 0
    for a in corrected_list:
        slug  = a.get("slug", "")
        body  = a.get("body", "")
        title = a.get("title", "")
        fail, reasons = is_still_fail(body, title, slug)
        if fail:
            print(f"  ❌ 修正後もFAIL（除外）: {slug} — {reasons}")
            excluded += 1
        else:
            final_articles.append(a)

    # 元の順序を保持
    slug_order = {a.get("slug", ""): i for i, a in enumerate(articles)}
    final_articles.sort(key=lambda a: slug_order.get(a.get("slug", ""), 999))

    with open(INPUT_PATH, "w", encoding="utf-8") as f:
        for a in final_articles:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    corrected_count = sum(1 for a in corrected_list if a.get("_corrected"))
    skipped_count   = sum(1 for a in corrected_list if a.get("_correction_skipped"))
    failed_count    = sum(1 for a in corrected_list if a.get("_correction_failed"))

    print("\n── 修正結果 ──")
    print(f"  ✅ 修正成功    : {corrected_count} 件")
    print(f"  ⚠️  ソースなしスキップ: {skipped_count} 件")
    print(f"  ❌ 修正失敗    : {failed_count} 件")
    print(f"  ❌ 最終FAIL除外: {excluded} 件")
    print(f"  → publish.py に渡す件数: {len(final_articles)} 件")


if __name__ == "__main__":
    asyncio.run(main())
