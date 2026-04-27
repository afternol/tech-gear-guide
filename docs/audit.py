# -*- coding: utf-8 -*-
"""
DeviceBrief 記事監査ツール (audit.py)
generate.py とは完全に独立した品質チェックシステム

入力: generated_articles.jsonl
出力: audit_report.md + audit_report.jsonl

チェック2段階:
  Phase 1: ルールベースチェック（機械的・即時）
  Phase 2: AIチェック（Claude APIでハルシネーション・品質検証）

ステータス:
  PASS  — 問題なし
  WARN  — 改善推奨（公開可能だが要注意）
  FAIL  — 公開不可・要修正
"""

import asyncio
import json
import re
import sys
import io
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import anthropic

# ─────────────────────────────────────────────
# 定数・閾値
# ─────────────────────────────────────────────

INPUT_PATH         = Path("generated_articles.jsonl")
REPORT_MD_PATH     = Path("audit_report.md")
REPORT_JSONL_PATH  = Path("audit_report.jsonl")

TITLE_MAX_LEN      = 70     # タイトル上限文字数
SEO_DESC_MAX_LEN   = 150    # SEO description 上限
BODY_MIN_LEN       = 500    # 本文下限
BODY_MAX_LEN       = 3000   # 本文上限（ゆるめ）
H2_MIN             = 3      # H2見出し最小数
H2_MAX             = 5      # H2見出し最大数
SOURCE_MIN         = 2      # 出典URL最小数

MODEL = "claude-sonnet-4-6"
AI_AUDIT_MAX_PARALLEL = 3

# ─────────────────────────────────────────────
# チェック結果型
# ─────────────────────────────────────────────

@dataclass
class CheckResult:
    rule_id: str
    label: str
    status: str          # "PASS" / "WARN" / "FAIL"
    detail: str = ""
    suggestion: str = ""

@dataclass
class ArticleAuditResult:
    article_index: int
    title: str
    article_type: str
    category: str
    overall: str         # PASS / WARN / FAIL（最悪ステータス）
    checks: list[CheckResult] = field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    pass_count: int = 0
    ai_audit_summary: str = ""

# ─────────────────────────────────────────────
# Phase 1: ルールベースチェック
# ─────────────────────────────────────────────

REQUIRED_META_KEYS = ["title", "slug", "category", "tags", "article_type", "body", "seo_description", "sources"]

# 推測をファクトとして断定する禁止パターン（日本語）
FORBIDDEN_FACT_PATTERNS = [
    (r"[〜〜]?でしょう[。」]", "「〜でしょう」は推測断定表現"),
    (r"と思われます[。」]",     "「と思われます」は推測断定表現"),
    (r"と考えられます[。」]",   "「と考えられます」は推測断定表現"),
    (r"に違いありません[。」]", "「に違いありません」は根拠なし断定"),
    (r"するはずです[。」]",     "「するはずです」は推測断定表現"),
    (r"間違いなく",             "「間違いなく」はソース確認なしの断定"),
]

# AIっぽい繰り返し表現（WARN）
AI_SOUNDING_PATTERNS = [
    (r"なお、", "「なお、」の多用はAIっぽい", 3),   # 3回以上でWARN
    (r"また、", "「また、」の多用はAIっぽい", 5),
    (r"さらに、", "「さらに、」の多用はAIっぽい", 4),
    (r"このように", "「このように」の多用はAIっぽい", 3),
]

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")


def check_metadata(article: dict) -> CheckResult:
    missing = [k for k in REQUIRED_META_KEYS if k not in article or not article[k]]
    if missing:
        return CheckResult("META_COMPLETE", "メタデータ完全性", "FAIL",
                           f"不足フィールド: {', '.join(missing)}",
                           "generate.pyのプロンプトを確認してメタデータが出力されているか確認")
    return CheckResult("META_COMPLETE", "メタデータ完全性", "PASS")


def check_title_length(article: dict) -> CheckResult:
    title = article.get("title", "")
    ln = len(title)
    if ln == 0:
        return CheckResult("TITLE_LENGTH", "タイトル長", "FAIL", "タイトルが空")
    if ln > TITLE_MAX_LEN:
        return CheckResult("TITLE_LENGTH", "タイトル長", "WARN",
                           f"{ln}字（上限{TITLE_MAX_LEN}字超過: +{ln - TITLE_MAX_LEN}字）",
                           f"タイトルを{TITLE_MAX_LEN}字以内に短縮してください")
    return CheckResult("TITLE_LENGTH", "タイトル長", "PASS", f"{ln}字")


def check_seo_desc(article: dict) -> CheckResult:
    desc = article.get("seo_description", "")
    ln = len(desc)
    if ln == 0:
        return CheckResult("SEO_DESC", "SEO description", "FAIL", "seo_descriptionが空")
    if ln > SEO_DESC_MAX_LEN:
        return CheckResult("SEO_DESC", "SEO description", "WARN",
                           f"{ln}字（上限{SEO_DESC_MAX_LEN}字超過）",
                           f"{SEO_DESC_MAX_LEN}字以内に短縮")
    return CheckResult("SEO_DESC", "SEO description", "PASS", f"{ln}字")


def check_body_length(article: dict) -> CheckResult:
    body = article.get("body", "")
    ln = len(body)
    if ln < BODY_MIN_LEN:
        return CheckResult("BODY_LENGTH", "本文文字数", "FAIL",
                           f"{ln:,}字（下限{BODY_MIN_LEN}字未満）",
                           "ソーステキストを再取得してgenerate.pyを再実行")
    if ln > BODY_MAX_LEN:
        return CheckResult("BODY_LENGTH", "本文文字数", "WARN",
                           f"{ln:,}字（上限{BODY_MAX_LEN}字超過）",
                           "冗長な部分を削除して圧縮することを検討")
    return CheckResult("BODY_LENGTH", "本文文字数", "PASS", f"{ln:,}字")


def check_h2_count(article: dict) -> CheckResult:
    body = article.get("body", "")
    h2_matches = re.findall(r"^## .+", body, re.MULTILINE)
    cnt = len(h2_matches)
    if cnt < H2_MIN or cnt > H2_MAX:
        status = "FAIL"
        suggestion = f"H2を{H2_MIN}〜{H2_MAX}個に調整してください"
    else:
        status = "PASS"
        suggestion = ""
    return CheckResult("H2_COUNT", "H2見出し数", status, f"{cnt}個（適正: {H2_MIN}〜{H2_MAX}個）", suggestion)


def check_sources(article: dict) -> CheckResult:
    sources = article.get("sources", [])
    if not isinstance(sources, list):
        return CheckResult("SOURCE_COUNT", "出典URL数", "FAIL", "sourcesフィールドが不正")

    valid_urls = [s for s in sources if isinstance(s, dict) and s.get("url", "").startswith("http")]
    cnt = len(valid_urls)

    invalid = [s for s in sources if isinstance(s, dict) and not s.get("url", "").startswith("http")]
    invalid_detail = f"、無効URL {len(invalid)}件" if invalid else ""

    if cnt < SOURCE_MIN:
        return CheckResult("SOURCE_COUNT", "出典URL数", "FAIL",
                           f"{cnt}本{invalid_detail}（必須: {SOURCE_MIN}本以上）",
                           "収集記事に出典URLが不足しています。ソースを追加してください")
    return CheckResult("SOURCE_COUNT", "出典URL数", "PASS", f"{cnt}本の有効URL{invalid_detail}")


def check_c_type_stars(article: dict) -> CheckResult:
    if article.get("article_type") != "C型リーク":
        return CheckResult("C_TYPE_STARS", "C型信頼度★", "PASS", "C型以外のためスキップ")
    body = article.get("body", "")
    reliability = article.get("source_reliability", 0)
    has_stars = "★" in body
    if not has_stars or reliability == 0:
        return CheckResult("C_TYPE_STARS", "C型信頼度★", "FAIL",
                           f"信頼度★評価なし（source_reliability={reliability}）",
                           "C型記事には必ず★評価（情報の確度）を本文冒頭に記載すること")
    return CheckResult("C_TYPE_STARS", "C型信頼度★", "PASS", f"★{reliability}/5")


def check_slug_format(article: dict) -> CheckResult:
    slug = article.get("slug", "")
    if not slug:
        return CheckResult("SLUG_FORMAT", "スラッグ形式", "FAIL", "slugが空")
    if not SLUG_PATTERN.match(slug):
        return CheckResult("SLUG_FORMAT", "スラッグ形式", "WARN",
                           f"不正な文字を含む可能性: '{slug}'",
                           "英小文字・数字・ハイフンのみで構成してください")
    return CheckResult("SLUG_FORMAT", "スラッグ形式", "PASS")


def check_forbidden_facts(article: dict) -> list[CheckResult]:
    body = article.get("body", "")
    results = []
    for pattern, label in FORBIDDEN_FACT_PATTERNS:
        matches = re.findall(pattern, body)
        if matches:
            results.append(CheckResult(
                "FORBIDDEN_FACT", f"推測ファクト化禁止（{label}）", "FAIL",
                f"{len(matches)}箇所検出: {matches[:3]}",
                "ソースにある表現か確認し、推測は「〜とされる」「〜と報告されている」等に修正"
            ))
    if not results:
        results.append(CheckResult("FORBIDDEN_FACT", "推測ファクト化禁止", "PASS"))
    return results


def check_ai_sounding(article: dict) -> list[CheckResult]:
    body = article.get("body", "")
    results = []
    for pattern, label, threshold in AI_SOUNDING_PATTERNS:
        cnt = len(re.findall(pattern, body))
        if cnt >= threshold:
            results.append(CheckResult(
                "AI_SOUNDING", f"AIっぽい表現（{label}）", "WARN",
                f"{cnt}回使用（閾値: {threshold}回）",
                f"使用回数を{threshold - 1}回以下に減らすか、自然な言い換えを使用"
            ))
    if not results:
        results.append(CheckResult("AI_SOUNDING", "AIっぽい表現チェック", "PASS"))
    return results


def check_category_valid(article: dict) -> CheckResult:
    valid = {"smartphone", "tablet", "windows", "cpu_gpu", "ai", "general"}
    cat = article.get("category", "")
    if cat not in valid:
        return CheckResult("CATEGORY", "カテゴリ値", "WARN",
                           f"未定義カテゴリ: '{cat}'",
                           f"有効なカテゴリ: {', '.join(sorted(valid))}")
    return CheckResult("CATEGORY", "カテゴリ値", "PASS", cat)


def run_rule_based_checks(article: dict) -> list[CheckResult]:
    results = []
    results.append(check_metadata(article))
    results.append(check_title_length(article))
    results.append(check_seo_desc(article))
    results.append(check_body_length(article))
    results.append(check_h2_count(article))
    results.append(check_sources(article))
    results.append(check_c_type_stars(article))
    results.append(check_slug_format(article))
    results.extend(check_forbidden_facts(article))
    results.extend(check_ai_sounding(article))
    results.append(check_category_valid(article))
    return results

# ─────────────────────────────────────────────
# Phase 2: AIベースチェック（ハルシネーション・品質）
# ─────────────────────────────────────────────

AI_AUDIT_SYSTEM = """\
あなたはDeviceBriefの品質監査官です。
AIが自動生成した日本語テック記事を審査します。
客観的・厳格に評価してください。
"""

def build_ai_audit_prompt(article: dict) -> str:
    sources_text = "\n".join(
        f"- [{s.get('title','')}]({s.get('url','')}) — {s.get('media', s.get('source_name',''))}"
        for s in article.get("sources", [])
    )
    return f"""\
以下の記事を審査してください。

【審査項目】
1. **ハルシネーション検出**: 出典URLに存在しない具体的な数値・仕様・引用が記事本文に含まれていないか
2. **推測の断定化**: ソースにない情報を事実として断定している箇所がないか
3. **日本語品質**: 不自然な日本語・AIっぽい反復表現・機械翻訳的な文体がないか
4. **専門示唆の有無**: 単なる翻訳に留まらず、なぜ重要か・日本市場への影響が含まれているか
5. **総合評価**: PASS（問題なし）/ WARN（改善推奨）/ FAIL（要修正）のいずれか

【記事タイトル】
{article.get('title', '')}

【記事タイプ】
{article.get('article_type', '')}

【出典】
{sources_text}

【記事本文（先頭2,000字）】
{article.get('body', '')[:2000]}

【出力フォーマット（JSON）】
{{
  "overall": "PASS|WARN|FAIL",
  "hallucination": {{"status": "PASS|WARN|FAIL", "detail": ""}},
  "speculation_as_fact": {{"status": "PASS|WARN|FAIL", "detail": ""}},
  "japanese_quality": {{"status": "PASS|WARN|FAIL", "detail": ""}},
  "expert_insight": {{"status": "PASS|WARN|FAIL", "detail": ""}},
  "summary": "総評を100字以内で"
}}
"""


async def run_ai_audit(
    client: anthropic.AsyncAnthropic,
    article: dict,
    sem: asyncio.Semaphore,
) -> tuple[list[CheckResult], str]:
    async with sem:
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=AI_AUDIT_SYSTEM,
                messages=[{"role": "user", "content": build_ai_audit_prompt(article)}],
            )
            text = response.content[0].text.strip()

            # JSON抽出
            m = re.search(r"\{[\s\S]+\}", text)
            if not m:
                return [], "AIチェック: JSONパース失敗"
            data = json.loads(m.group(0))

            checks = []
            label_map = {
                "hallucination":       "ハルシネーション",
                "speculation_as_fact": "推測ファクト化",
                "japanese_quality":    "日本語品質",
                "expert_insight":      "専門示唆の有無",
            }
            for key, label in label_map.items():
                item = data.get(key, {})
                checks.append(CheckResult(
                    f"AI_{key.upper()}", f"AI審査: {label}",
                    item.get("status", "WARN"),
                    item.get("detail", ""),
                ))

            summary = data.get("summary", "")
            return checks, summary

        except Exception as e:
            return [], f"AIチェックエラー: {e}"

# ─────────────────────────────────────────────
# 総合判定
# ─────────────────────────────────────────────

def determine_overall(checks: list[CheckResult]) -> str:
    statuses = [c.status for c in checks]
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"

# ─────────────────────────────────────────────
# レポート生成
# ─────────────────────────────────────────────

STATUS_ICON = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}

def build_md_report(results: list[ArticleAuditResult], run_at: str) -> str:
    lines = [
        "# DeviceBrief 記事監査レポート",
        f"\n実施日時: {run_at}",
        f"対象記事数: {len(results)} 件",
        "",
        "---",
        "",
        "## サマリー",
        "",
        f"| # | タイトル | タイプ | 結果 | FAIL | WARN |",
        f"|---|---|---|---|---|---|",
    ]
    for r in results:
        icon = STATUS_ICON[r.overall]
        lines.append(f"| {r.article_index+1} | {r.title[:40]}... | {r.article_type} | {icon} {r.overall} | {r.fail_count} | {r.warn_count} |")

    lines += ["", "---", "", "## 詳細チェック結果", ""]

    for r in results:
        icon = STATUS_ICON[r.overall]
        lines.append(f"### 記事{r.article_index+1}: {icon} {r.overall}")
        lines.append(f"**{r.title}**  ")
        lines.append(f"タイプ: {r.article_type} / カテゴリ: {r.category}")
        lines.append("")

        for c in r.checks:
            si = STATUS_ICON[c.status]
            line = f"- {si} `{c.rule_id}` **{c.label}**"
            if c.detail:
                line += f" — {c.detail}"
            lines.append(line)
            if c.suggestion and c.status != "PASS":
                lines.append(f"  > 対策: {c.suggestion}")

        if r.ai_audit_summary:
            lines.append(f"\n**AI総評**: {r.ai_audit_summary}")

        lines.append("")

    # 全体統計
    total_fail = sum(r.fail_count for r in results)
    total_warn = sum(r.warn_count for r in results)
    publish_ok = sum(1 for r in results if r.overall == "PASS")
    lines += [
        "---",
        "## 全体統計",
        "",
        f"- 公開可能（PASS）: **{publish_ok}件**",
        f"- 要注意（WARN）: **{sum(1 for r in results if r.overall == 'WARN')}件**",
        f"- 要修正（FAIL）: **{sum(1 for r in results if r.overall == 'FAIL')}件**",
        f"- 合計FAIL項目数: **{total_fail}件**",
        f"- 合計WARN項目数: **{total_warn}件**",
    ]
    return "\n".join(lines)

# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

async def main():
    if not INPUT_PATH.exists():
        print(f"入力ファイルが見つかりません: {INPUT_PATH}")
        return

    articles = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                articles.append(json.loads(line))

    print(f"監査対象: {len(articles)} 件")
    print("=" * 60)

    client = anthropic.AsyncAnthropic()
    sem = asyncio.Semaphore(AI_AUDIT_MAX_PARALLEL)
    audit_results: list[ArticleAuditResult] = []

    # Phase1 + Phase2 を並列実行
    async def audit_one(idx: int, article: dict) -> ArticleAuditResult:
        title = article.get("title", f"記事{idx+1}")
        print(f"  [{idx+1}] Phase1チェック中: {title[:50]}...")

        # Phase 1: ルールベース
        rule_checks = run_rule_based_checks(article)

        # Phase 2: AIチェック
        ai_checks, ai_summary = await run_ai_audit(client, article, sem)

        all_checks = rule_checks + ai_checks
        overall = determine_overall(all_checks)
        fail_cnt = sum(1 for c in all_checks if c.status == "FAIL")
        warn_cnt = sum(1 for c in all_checks if c.status == "WARN")
        pass_cnt = sum(1 for c in all_checks if c.status == "PASS")

        result = ArticleAuditResult(
            article_index=idx,
            title=title,
            article_type=article.get("article_type", ""),
            category=article.get("category", ""),
            overall=overall,
            checks=all_checks,
            fail_count=fail_cnt,
            warn_count=warn_cnt,
            pass_count=pass_cnt,
            ai_audit_summary=ai_summary,
        )

        icon = STATUS_ICON[overall]
        print(f"  [{idx+1}] {icon} {overall} — FAIL:{fail_cnt} WARN:{warn_cnt} PASS:{pass_cnt}")
        return result

    tasks = [audit_one(i, a) for i, a in enumerate(articles)]
    audit_results = await asyncio.gather(*tasks)

    # レポート出力
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md_report = build_md_report(list(audit_results), run_at)
    REPORT_MD_PATH.write_text(md_report, encoding="utf-8")
    print(f"\nレポート出力: {REPORT_MD_PATH}")

    with open(REPORT_JSONL_PATH, "w", encoding="utf-8") as f:
        for r in audit_results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    print(f"詳細データ: {REPORT_JSONL_PATH}")

    # コンソールサマリー
    print("\n" + "=" * 60)
    print("監査サマリー")
    print("=" * 60)
    for r in audit_results:
        print(f"  {STATUS_ICON[r.overall]} [{r.article_type}] {r.title[:55]}")
        if r.overall != "PASS":
            for c in r.checks:
                if c.status in ("FAIL", "WARN"):
                    print(f"       {STATUS_ICON[c.status]} {c.label}: {c.detail[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
