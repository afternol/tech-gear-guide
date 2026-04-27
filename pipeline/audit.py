# -*- coding: utf-8 -*-
"""
Tech Gear Guide — audit.py
generated_articles.jsonl の品質チェック
- タイトル・スラッグ・本文の基本検証
- ハルシネーション兆候チェック（疑わしい表現の検出）
- 結果を audit_report.jsonl に出力
"""

import json, re, sys, io
from pathlib import Path
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

INPUT_PATH  = Path("generated_articles.jsonl")
REPORT_PATH = Path("audit_report.jsonl")

# 警告: ソース記事にない可能性が高い典型的な推測表現
HALLUCINATION_PATTERNS = [
    r"(?:と(?:思われ|考えられ|推測され|予想され)ます)",
    r"(?:おそらく|恐らく).*(?:でしょう|と思います)",
    r"詳細は不明ですが",
    r"情報によると.*と言われています",
]

MIN_BODY_LEN       = 1200   # これ未満はFAIL（公開しない）
MIN_BODY_LEN_WARN  = 1500   # これ未満はWARN
MIN_TITLE_LEN      = 15
MAX_TITLE_LEN      = 80
MIN_FACTS          = 2      # 数値・固有名詞が少なすぎる記事をWARN


def audit_article(article: dict) -> dict:
    issues   = []
    warnings = []

    title = article.get("title", "")
    slug  = article.get("slug", "")
    body  = article.get("body", "")
    seo   = article.get("seo_description", "")
    cat   = article.get("category", "")

    # タイトル検証
    if len(title) < MIN_TITLE_LEN:
        issues.append(f"タイトルが短すぎます（{len(title)}文字）")
    if len(title) > MAX_TITLE_LEN:
        warnings.append(f"タイトルが長すぎます（{len(title)}文字）")

    # スラッグ検証
    if not slug or not re.match(r'^[a-z0-9\-]+$', slug):
        issues.append(f"スラッグが不正です: {slug}")
    if len(slug) > 80:
        warnings.append(f"スラッグが長すぎます（{len(slug)}文字）")

    # 本文検証
    if len(body) < MIN_BODY_LEN:
        issues.append(f"本文が短すぎます（{len(body)}文字・最低{MIN_BODY_LEN}字必要）")
    elif len(body) < MIN_BODY_LEN_WARN:
        warnings.append(f"本文がやや短いです（{len(body)}文字・推奨{MIN_BODY_LEN_WARN}字以上）")

    # 情報密度チェック（数値・英数字固有名詞）
    numbers = re.findall(r'\d+(?:[.,]\d+)?(?:\s*(?:mm|GB|TB|MHz|GHz|W|%|円|ドル|fps|ms))?', body)
    proper_nouns = re.findall(r'[A-Z][a-zA-Z0-9]{2,}(?:\s+[A-Z][a-zA-Z0-9]+)*', body)
    if len(numbers) + len(proper_nouns) < MIN_FACTS:
        warnings.append(f"情報密度が低い可能性（数値:{len(numbers)} 固有名詞:{len(proper_nouns)}）")

    # SEO説明
    if not seo:
        warnings.append("SEO説明がありません")
    elif len(seo) > 160:
        warnings.append(f"SEO説明が長すぎます（{len(seo)}文字）")

    # カテゴリ検証
    valid_cats = {"smartphone","tablet","windows","cpu_gpu","ai","xr","wearable","general"}
    if cat not in valid_cats:
        issues.append(f"不正なカテゴリ: {cat}")

    # 出典チェック
    if "**出典**" not in body and "## 出典" not in body:
        warnings.append("出典セクションが見つかりません")

    # ハルシネーション兆候チェック
    for pat in HALLUCINATION_PATTERNS:
        if re.search(pat, body):
            warnings.append(f"推測表現の可能性: {pat}")

    # だ・である調チェック
    da_de_aru = re.findall(r'[^。！？\n]{5,}(?:だ。|である。|だろう。)', body)
    if da_de_aru:
        warnings.append(f"だ・である調の文末が {len(da_de_aru)} 箇所あります")

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")

    return {
        "slug":     slug,
        "title":    title[:60],
        "category": cat,
        "body_len": len(body),
        "status":   status,
        "issues":   issues,
        "warnings": warnings,
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    if not INPUT_PATH.exists():
        print(f"入力ファイルが見つかりません: {INPUT_PATH}")
        return

    articles = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                articles.append(json.loads(line))

    print(f"監査対象: {len(articles)} 件")
    reports  = [audit_article(a) for a in articles]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        for r in reports:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pass_  = sum(1 for r in reports if r["status"] == "PASS")
    warn_  = sum(1 for r in reports if r["status"] == "WARN")
    fail_  = sum(1 for r in reports if r["status"] == "FAIL")

    print(f"PASS: {pass_} / WARN: {warn_} / FAIL: {fail_}")

    if fail_ > 0:
        print("\n── FAIL 詳細 ──")
        for r in reports:
            if r["status"] == "FAIL":
                print(f"  [{r['slug']}] {r['issues']}")

    # FAIL記事を generated_articles.jsonl から除外して上書き
    if fail_ > 0:
        passed = [a for a, r in zip(articles, reports) if r["status"] != "FAIL"]
        with open(INPUT_PATH, "w", encoding="utf-8") as f:
            for a in passed:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        print(f"FAIL {fail_}件を除外 → {len(passed)}件を publish.py に渡します")

    # FAILが全体の50%超えたらパイプライン停止
    if len(articles) > 0 and fail_ / len(articles) > 0.5:
        print("FAILが50%を超えています。パイプラインを停止します。")
        sys.exit(1)


if __name__ == "__main__":
    main()
