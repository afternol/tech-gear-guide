# -*- coding: utf-8 -*-
"""
Tech Gear Guide — audit.py (v2)
generated_articles.jsonl の品質チェック
- 基本構造チェック
- ソースグラウンディングチェック（数値・製品名をソースと照合）
- AI監査（Claude がソース vs 記事を比較して事実誤りを検出）
- FAIL/WARN 記事の詳細をレポートとして出力（除外は correct.py に委ねる）
"""

import asyncio
import argparse
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
SOURCE_PATH = Path("collected_articles.jsonl")
REPORT_PATH = Path("audit_report.jsonl")

MODEL        = "claude-sonnet-4-6"
MAX_PARALLEL = 3

# 数値+単位（2桁以上、意味のある単位）
_NUM_UNIT_RE = re.compile(
    r'\b\d{2,}(?:[.,]\d+)?\s*'
    r'(?:nm|GB|TB|MB|GHz|MHz|Wh?|mAh|mm|fps|ms|コア|スレッド)',
    re.IGNORECASE,
)

# 製品名・型番
_MODEL_RE = re.compile(
    r'(?:'
    r'iPhone\s*\d{1,2}(?:\s*(?:Pro|Plus|Max))?'
    r'|iPad\s*(?:Pro|Air|mini)\s*\d*'
    r'|Galaxy\s*[SZA]\d+(?:\s*(?:Ultra|Plus|FE))?'
    r'|Pixel\s*\d+(?:\s*(?:Pro|a))?'
    r'|RTX\s*\d{4}(?:\s*(?:Ti|Super))?'
    r'|RX\s*\d{4}(?:\s*XT)?'
    r'|Ryzen\s*\d\s*\d{4}[XG]?'
    r'|Core\s*[iU]\d-\d{4,5}'
    r'|Snapdragon\s*\d{3,4}[A-Z]?'
    r'|M\d\s*(?:Pro|Max|Ultra)?'
    r'|A\d{2}\s*Bionic'
    r')',
    re.IGNORECASE,
)

HALLUCINATION_PATTERNS = [
    (r"と(?:思われ|考えられ|推測され|予想され)ます",          "推測表現"),
    (r"おそらく.{0,20}(?:でしょう|と思います)",               "おそらく系推測"),
    (r"詳細は不明ですが",                                      "不明断定"),
    (r"情報によると.{0,30}と言われています",                   "伝聞曖昧"),
    (r"と(?:噂|うわさ)されています(?!。.*出典)",               "噂表現（出典なし）"),
]

MIN_BODY_LEN      = 1200
MIN_BODY_LEN_WARN = 1500
MIN_TITLE_LEN     = 15
MAX_TITLE_LEN     = 80

# ─────────────────────────────────────────────
# ソース照合
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

def _source_bodies(article: dict, source_map: dict) -> list[str]:
    urls = [s.get("url", "") for s in article.get("sources", [])]
    return [source_map[u] for u in urls if u in source_map]

def check_grounding(article_body: str, source_bodies: list[str]) -> list[str]:
    """記事にあってソースにない数値・製品名を返す（警告用）"""
    source_text = " ".join(source_bodies).lower()
    ungrounded: list[str] = []

    for m in _NUM_UNIT_RE.finditer(article_body):
        num_str = m.group().strip()
        num_core = re.search(r'\d+', num_str)
        if num_core and num_core.group() not in source_text:
            ungrounded.append(num_str)

    for m in _MODEL_RE.finditer(article_body):
        model = m.group().strip()
        if model.lower() not in source_text:
            ungrounded.append(model)

    return list(dict.fromkeys(ungrounded))[:5]

# ─────────────────────────────────────────────
# AI監査
# ─────────────────────────────────────────────

_AI_SYSTEM = (
    "あなたはTech Gear Guideの事実確認担当編集者です。"
    "記事とソースを比較し、事実の誤りを特定します。"
    "必ずJSON形式のみで回答してください。"
)

_AI_PROMPT = """\
以下の【生成記事】と【ソース記事】を比較し、事実確認してください。

確認項目:
1. ソースにない数値・スペック・日付が記事に含まれていないか
2. 製品名・モデル名・社名の誤りがないか
3. ソースと矛盾する表現がないか（例: ソースは「3nm」だが記事は「4nm」）
4. 推測・憶測をソース情報として断定していないか

JSON形式のみで回答（コードブロック不要）:
{{"verdict": "accurate"|"minor_issues"|"major_issues", "issues": ["具体的な問題（例: ソースにない○○という数値が記載されている）"], "confidence": 0.0-1.0}}

【ソース記事】
{source_body}

【生成記事】
{article_body}
"""

async def _no_source_ai() -> dict:
    return {"verdict": "no_source", "issues": [], "confidence": 0.0}

async def ai_judge_one(
    client: anthropic.AsyncAnthropic,
    article_body: str,
    source_body: str,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        prompt = _AI_PROMPT.format(
            source_body=source_body[:3000],
            article_body=article_body[:3000],
        )
        try:
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=_AI_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"  ⚠️  AI監査エラー: {e}")
        return {"verdict": "unknown", "issues": [], "confidence": 0.0}

async def run_ai_judges(
    client: anthropic.AsyncAnthropic,
    articles: list[dict],
    source_map: dict,
) -> list[dict]:
    sem   = asyncio.Semaphore(MAX_PARALLEL)
    tasks = []
    for a in articles:
        bodies = _source_bodies(a, source_map)
        if bodies:
            tasks.append(ai_judge_one(client, a.get("body", ""), bodies[0], sem))
        else:
            tasks.append(_no_source_ai())
    return list(await asyncio.gather(*tasks))

# ─────────────────────────────────────────────
# 単体記事監査
# ─────────────────────────────────────────────

def audit_article(
    article: dict,
    source_map: dict,
    ai_result: Optional[dict] = None,
) -> dict:
    issues:   list[str] = []
    warnings: list[str] = []

    title = article.get("title", "")
    slug  = article.get("slug", "")
    body  = article.get("body", "")
    seo   = article.get("seo_description", "")
    cat   = article.get("category", "")

    # ── 基本構造 ──
    if len(title) < MIN_TITLE_LEN:
        issues.append(f"タイトルが短すぎます（{len(title)}文字）")
    if len(title) > MAX_TITLE_LEN:
        warnings.append(f"タイトルが長すぎます（{len(title)}文字）")

    if not slug or not re.match(r'^[a-z0-9\-]+$', slug):
        issues.append(f"スラッグが不正: {slug}")
    elif len(slug) > 80:
        warnings.append(f"スラッグが長すぎます（{len(slug)}文字）")

    if len(body) < MIN_BODY_LEN:
        issues.append(f"本文が短すぎます（{len(body)}文字、最低{MIN_BODY_LEN}字）")
    elif len(body) < MIN_BODY_LEN_WARN:
        warnings.append(f"本文がやや短い（{len(body)}文字）")

    valid_cats = {"smartphone", "tablet", "windows", "cpu_gpu", "ai", "xr", "wearable", "general"}
    if cat not in valid_cats:
        issues.append(f"不正なカテゴリ: {cat}")

    if "**出典**" not in body and "## 出典" not in body:
        warnings.append("出典セクションが見つかりません")

    if not seo:
        warnings.append("SEO説明がありません")
    elif len(seo) > 160:
        warnings.append(f"SEO説明が長すぎます（{len(seo)}文字）")

    # ── ハルシネーション兆候（パターン） ──
    for pat, label in HALLUCINATION_PATTERNS:
        if re.search(pat, body):
            warnings.append(f"推測表現（{label}）")

    # ── 語調 ──
    da = re.findall(r'[^。！？\n]{5,}(?:だ。|である。|だろう。)', body)
    if len(da) >= 2:
        warnings.append(f"だ・である調が {len(da)} 箇所あります")

    # ── グラウンディング ──
    src_bodies = _source_bodies(article, source_map)
    if src_bodies:
        ungrounded = check_grounding(body, src_bodies)
        if ungrounded:
            warnings.append(f"ソースで未確認の記述: {', '.join(ungrounded[:3])}")
    else:
        warnings.append("ソース本文が取得できていません（grounding不可）")

    # ── AI監査結果 ──
    ai_verdict = None
    if ai_result:
        verdict    = ai_result.get("verdict", "unknown")
        ai_verdict = verdict
        for issue in ai_result.get("issues", []):
            if verdict == "major_issues":
                issues.append(f"[AI] {issue}")
            elif verdict == "minor_issues":
                warnings.append(f"[AI] {issue}")

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")

    return {
        "slug":       slug,
        "title":      title[:60],
        "category":   cat,
        "body_len":   len(body),
        "status":     status,
        "issues":     issues,
        "warnings":   warnings,
        "ai_verdict": ai_verdict,
        "has_source": bool(src_bodies),
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ai-check", action="store_true", help="AI監査を省略（コスト節約）")
    args = parser.parse_args()

    if not INPUT_PATH.exists():
        print(f"入力ファイルが見つかりません: {INPUT_PATH}")
        return

    articles: list[dict] = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                articles.append(json.loads(line))

    print(f"監査対象: {len(articles)} 件")

    source_map = load_source_map()
    print(f"ソース: {len(source_map)} 件ロード")

    ai_results: list[Optional[dict]]
    if not args.no_ai_check and articles:
        print("AI監査を実行中...")
        client     = anthropic.AsyncAnthropic()
        ai_results = await run_ai_judges(client, articles, source_map)
    else:
        if args.no_ai_check:
            print("AI監査: スキップ（--no-ai-check）")
        ai_results = [None] * len(articles)

    reports = [
        audit_article(a, source_map, ai_r)
        for a, ai_r in zip(articles, ai_results)
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        for r in reports:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pass_ = sum(1 for r in reports if r["status"] == "PASS")
    warn_ = sum(1 for r in reports if r["status"] == "WARN")
    fail_ = sum(1 for r in reports if r["status"] == "FAIL")

    print(f"\nPASS: {pass_} / WARN: {warn_} / FAIL: {fail_}")

    if fail_:
        print("\n── FAIL 詳細 ──")
        for r in reports:
            if r["status"] == "FAIL":
                print(f"  [{r['slug']}]")
                for i in r["issues"]:
                    print(f"    ✗ {i}")

    if warn_:
        print("\n── WARN 詳細 ──")
        for r in reports:
            if r["status"] == "WARN":
                print(f"  [{r['slug']}]")
                for w in r["warnings"]:
                    print(f"    △ {w}")

    # FAIL/WARN は correct.py が修正を試みる（ここでは除外しない）
    print(f"\n→ correct.py に渡します（FAIL {fail_}件・WARN {warn_}件を修正対象とします）")

    if len(articles) > 0 and fail_ / len(articles) > 0.7:
        print("FAILが70%超。パイプラインを停止します。")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
