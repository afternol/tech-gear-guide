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

# 未来イベントの文脈で使われる語句（発売・発表・リリース等）
_FUTURE_CONTEXT_RE = re.compile(
    r'(\d{4})年.{0,40}(?:発売|発表|リリース|公開|開催|登場|予定|実装)',
)

# 内部スコア混入パターン
_INTERNAL_SCORE_RE = re.compile(r'\b[1-5]/5(?:と|で|に|は|の)')
_STAR_RATING_RE    = re.compile(r'[★☆]{3,}')

# バッチ間汚染（同日に別ソースを参照）
_CROSS_BATCH_RE = re.compile(
    r'同日[にも].{0,40}(?:報じ|発表|リリース|公開|明らか)',
)

# "up to N%" パターン（magnitude distortion 検出用）
_UP_TO_PCT_RE = re.compile(r'up to (\d+)\s*%', re.IGNORECASE)
_UP_TO_X_RE   = re.compile(r'(?:up to|as many as|as much as) (\d+)', re.IGNORECASE)

# ソース内のヘッジング表現
_HEDGE_EN_RE = re.compile(
    r'\b(?:may|might|could|reportedly|allegedly|rumored|leaked|possibly|expected to|up to|as many as)\b',
    re.IGNORECASE,
)
# 記事内の日本語ヘッジング表現
_HEDGE_JA_PATTERNS = [
    "かもしれません", "可能性があります", "と報じられ", "とされ", "とみられ",
    "リーク", "噂", "予想され", "見込まれ", "最大", "の可能性",
]

# ─────────────────────────────────────────────
# 日付整合性チェック
# ─────────────────────────────────────────────

def check_date_plausibility(body: str, published_at: str) -> list[str]:
    """published_at と矛盾する年号を検出する（年号ハルシネーション対策）"""
    issues: list[str] = []
    try:
        pub_year = datetime.fromisoformat(published_at).year
    except Exception:
        return issues

    for m in _FUTURE_CONTEXT_RE.finditer(body):
        mentioned_year = int(m.group(1))
        if mentioned_year < pub_year:
            context = body[m.start(): m.start() + 60].replace("\n", " ")
            issues.append(
                f"年号が過去にずれている可能性: 「{mentioned_year}年」（記事公開: {pub_year}年）"
                f" — 「{context[:50]}」"
            )
    return issues

# ─────────────────────────────────────────────
# 内部メタデータ混入チェック
# ─────────────────────────────────────────────

def check_metadata_leaks(body: str) -> list[str]:
    """旧実装の内部スコア・星表示が本文に混入していないか検出"""
    issues: list[str] = []
    if _INTERNAL_SCORE_RE.search(body):
        issues.append("内部ソーススコア（X/5）が本文に混入している可能性があります")
    if _STAR_RATING_RE.search(body):
        issues.append("信頼度星表示（★☆×3以上）が本文に残っている可能性があります")
    return issues

# ─────────────────────────────────────────────
# 追加チェック関数群
# ─────────────────────────────────────────────

def check_cross_batch_contamination(body: str) -> list[str]:
    """バッチ内別記事への言及パターンを検出（FAILレベル）"""
    if _CROSS_BATCH_RE.search(body):
        return ["「同日に〜が報じ/発表」パターンを検出。別記事のトピックを参照している可能性があります"]
    return []

def check_title_body_consistency(title: str, body: str) -> list[str]:
    """タイトル内の数値が本文に存在するか確認"""
    warnings = []
    for m in re.finditer(r'(\d{2,})(?:[.,]\d+)?(?:\s*%)?', title):
        num = m.group(1)
        if num not in body:
            warnings.append(f"タイトルの数値「{num}」が本文に見当たりません")
    return warnings[:2]

def check_magnitude_distortion(body: str, source_bodies: list[str]) -> list[str]:
    """ソースの「up to N%」が記事で「最大」なしの「N%」に断定変換されていないか確認"""
    source_text = " ".join(source_bodies)
    warnings    = []
    for m in _UP_TO_PCT_RE.finditer(source_text):
        num = m.group(1)
        # 記事でこの数値が「最大」や「約」なしで登場するか
        strict_re = re.compile(rf'(?<![最大約\d]){re.escape(num)}%')
        if strict_re.search(body):
            warnings.append(
                f"ソースの「up to {num}%」が記事で「最大」なしの「{num}%」に断定変換されている可能性があります"
            )
    return warnings[:2]

def check_hedging_preservation(body: str, source_bodies: list[str]) -> list[str]:
    """ソースに不確定表現が多いのに記事では断定調になっていないか確認"""
    source_text  = " ".join(source_bodies)
    hedge_count  = len(_HEDGE_EN_RE.findall(source_text))
    if hedge_count < 3:
        return []
    has_hedge_in_article = any(h in body for h in _HEDGE_JA_PATTERNS)
    if not has_hedge_in_article:
        return [
            f"ソースに不確定表現（may/reportedly等）が{hedge_count}箇所あるが、"
            "記事では断定調になっている可能性があります"
        ]
    return []

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
記事公開日は {published_at} です。

確認項目（重要度順）:

1.【年号・日付の誤り ★最重要】
   - 発売日・発表日・リリース日の年号がソースと一致しているか
   - ソースが2026年4月の記事なのに記事本文が「2025年」と書いていないか

2.【否定・未確認事項の断定変換 ★最重要】
   - ソースで「not confirmed」「denied」「ruled out」「not yet」の情報が記事で断定されていないか
   - 「まだ発表されていない」が「発表された」に変わっていないか

3.【ヘッジング表現の消去 ★重要】
   - ソースの「may」「might」「reportedly」「allegedly」「up to」「as many as」が
     記事で「最大〜」「〜の可能性」等の不確定表現なしで断定されていないか
   - 「最大60%高速化」がソースなのに記事で「60%高速化」と断定になっていないか

4.【ソース外トピックへの言及 ★重要】
   - 「同日に○○が報じられた」など、このソース記事にない別のニュース・製品への言及がないか
   - ソース記事に書かれていない競合製品との比較がないか

5.【引用符の捏造】
   - 記事内の「〜と○○氏は述べています」等の直接引用がソースに実在するか
   - ソースにない発言を「」で引用していないか

6.【数値・スペックの誤り】
   - ソースにない数値・スペック・パーセンテージが追加されていないか
   - ソースの数値と異なる値（例: ソース30%→記事60%）がないか

7.【通貨換算の捏造】
   - ソースに円換算がないのに記事で「約○○万円」等の円換算を追加していないか

8.【固有名詞の誤り】
   - 製品名・モデル名・人物名・メディア名・チャンネル名が正しいか
   - ソース記事がさらに別メディアを引用している場合（Neowin via Windows Central等）、
     帰属先の表記が正しいか

9.【投機的合成】
   - ソースの複数情報を組み合わせてソースが明示していない新しい主張を導いていないか
   （例: ソースA「薄型化」＋ソースB「バッテリー増量」→記事「薄型化しながらバッテリー増量」という未言及の結論）

10.【タイトルと本文の整合性】
    - タイトルに数値・スペックが含まれる場合、本文でも同じ数値が正しく使われているか

JSON形式のみで回答（コードブロック不要）:
{{"verdict": "accurate"|"minor_issues"|"major_issues", "issues": ["具体的な問題（例: ソースは2026年7月発売と書いているが記事では2025年7月22日と誤記）"], "confidence": 0.0-1.0}}

【ソース記事】
{source_body}

【生成記事（公開日: {published_at}）】
{article_body}
"""

async def _no_source_ai() -> dict:
    return {"verdict": "no_source", "issues": [], "confidence": 0.0}

async def ai_judge_one(
    client: anthropic.AsyncAnthropic,
    article_body: str,
    source_body: str,
    published_at: str,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        prompt = _AI_PROMPT.format(
            source_body=source_body[:4500],
            article_body=article_body,         # 記事は全文使用
            published_at=published_at[:10],
        )
        try:
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=900,
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
        bodies       = _source_bodies(a, source_map)
        published_at = a.get("published_at", datetime.now(timezone.utc).isoformat())
        if bodies:
            tasks.append(ai_judge_one(client, a.get("body", ""), bodies[0], published_at, sem))
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

    # ── 年号バリデーション ──
    published_at = article.get("published_at", "")
    date_issues  = check_date_plausibility(body, published_at)
    for di in date_issues:
        issues.append(di)

    # ── 内部メタデータ混入チェック ──
    leak_issues = check_metadata_leaks(body)
    for li in leak_issues:
        issues.append(li)

    # ── バッチ間汚染チェック ──
    for c in check_cross_batch_contamination(body):
        issues.append(c)

    # ── タイトル・本文整合性 ──
    for w in check_title_body_consistency(title, body):
        warnings.append(w)

    # ── グラウンディング ──
    src_bodies = _source_bodies(article, source_map)
    if src_bodies:
        ungrounded = check_grounding(body, src_bodies)
        if ungrounded:
            warnings.append(f"ソースで未確認の記述: {', '.join(ungrounded[:3])}")

        # ── magnitude distortion ──
        for w in check_magnitude_distortion(body, src_bodies):
            warnings.append(w)

        # ── hedging preservation ──
        for w in check_hedging_preservation(body, src_bodies):
            warnings.append(w)
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
