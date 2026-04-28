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

from dotenv import load_dotenv
load_dotenv()

import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

INPUT_PATH  = Path("generated_articles.jsonl")
REPORT_PATH = Path("audit_report.jsonl")
SOURCE_PATH = Path("collected_articles.jsonl")

MODEL        = "claude-sonnet-4-6"
MAX_PARALLEL = 3

MIN_BODY_LEN = 1200

VALID_CATEGORIES = {"smartphone", "windows", "cpu_gpu", "ai", "tablet", "xr", "wearable", "general"}

# ─────────────────────────────────────────────
# プロンプト
# ─────────────────────────────────────────────

_FACT_SYSTEM = """\
あなたはTech Gear Guideの事実確認・修正担当編集長です。
ソース記事の情報のみを根拠に、指摘された問題点を修正してください。
出力は必ず指定のMETAフォーマットで行ってください。
"""

_FACT_CORRECT_PROMPT = """\
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
- category は必ず以下の許容値のいずれかにする: smartphone / windows / cpu_gpu / ai / tablet / xr / wearable / general
  不正なカテゴリ（app・electronics_diy・mobile 等）が指定されている場合、最も近い許容値に変更する
- ソースにない情報は追加しない（★最重要・最も厳守すべきルール）
  特に以下は絶対禁止：
  ① ソース記事に登場しないメディア名・出典名（9to5Mac / HowToGeek / Axios / TechCrunch / MacRumors 等）を新たに引用・言及すること
  ② ソース記事に書かれていないURLを追加すること
  ③ ソース記事に存在しない数値・スペック・統計を補完すること
  ④ ソース記事にない企業の戦略・意図の解説を追加すること
  ⑤ ソース記事にない競合サービスの詳細（価格・機能・制約等）を追加すること
  修正とは「誤った情報を削除・訂正すること」であり「新しい情報を足すこと」ではない。
- ソースにある情報は削除しない（必要な事実を残す）
- です・ます調を維持する
- 本文は最低 {min_len} 文字以上
- 年号の誤り（例: 2025年と書かれているが正しくは2026年）は特に注意して修正する
- 「X/5と評価」「★★★☆☆」などの内部スコア表現は削除する
- ソース記事にない別製品・別トピックへの言及を削除する
- ソース内のヘッジング表現（may/might/reportedly/up to等）は不確定表現のまま保持する
- ソースの主語・範囲を拡大しない（スタートメニューの話をWindows 11全体に拡大しない等）
- ソースメディアの解釈・計算値を企業の発言として断定している場合は「（メディア名）は〜と報じている」に修正する
  例: 「TSMCは48倍と述べた」→「Tom's Hardwareは、TSMCロードマップを基に最大48倍と報じている」
- 数量の単位誤変換を修正する: ソースの「records/entries」を「顧客数/人数」にしている場合は「件のレコード」に戻す
- メディアの評価語（矮小化・過小評価・隠蔽等）に帰属が付いていない場合は「（メディア名）は〜と報じている」を追加する
- ソース記事のメタ情報（著者名・文字数・英語カテゴリ名・関連キーワード・記事URL等）が本文に含まれている場合は完全に削除する
  例: 「Brady Snyder氏（Android Authority）」「約1,338語（英語）」「Features」「関連キーワード:」「記事URL:」→ すべて削除
- アナリスト・リーク情報源の主張が断定形になっている場合、帰属表現に修正する
  NG: 「OpenAIがMediaTekとチップを開発中」
  OK: 「Kuo氏によると、OpenAIがMediaTekとチップを開発している可能性があるとされる」
- タイトル・リードがソースの確信度を超えた断定になっている場合は「か」「可能性」「示唆」等の不確定表現に戻す
- 「上位機に勝つ」「完全に上回る」等の無条件優位表現は、ソースが特定条件での優位しか述べていない場合は条件を付ける
  例: 「バッテリー容量・軽量性・物理SIM対応など実用面4点でPixel 10aが優位」
- レビュアーの主観・評価が「証明」「実証」等の客観語で書かれている場合、「○○氏は〜と評価している」に修正する
- 「ゼロにする」「完全に解消」等の絶対語がソース根拠なしに使われている場合、「大幅に削減できる」等の表現に変える
- 企業が明言していない戦略・意図の推測が断定されている場合、「と読める」「との見方もある」を付ける
- ソースにない詳細説明・役割分担の推測が本文に含まれている場合は削除し、「詳細は出典元を参照」で置き換える
- タイトルで「N個/N点/Nつ/N選/Nポイント/N理由」等と数を宣言しているのに本文で列挙していない場合は修正する
  ① ソースにそのN件の内容が書かれている場合 → 本文で番号付き箇条書き・H2見出しで明示する
    例: 「4つのポイント」が宣言されており、ソースに「フラット背面・183g・5,100mAh・物理SIM」がある
        → 本文の該当箇所に「① フラット背面デザイン」「② 軽量性（183g）」等と明示する
  ② ソースにその数の内容が書かれていない場合 → タイトルを「いくつかのポイント」「複数の優位点」等に変更する
- ソースにある具体的な数値（重量・バッテリー容量・スペック・価格等）が記事にない場合は追加する
  例: ソースにPixel 10aが183g・Pixel 10が204g・バッテリー5,100mAh vs 4,970mAhとある場合は必ず記事に含める
- 地域限定仕様（米国版のみ等）がソースにあるのに記事で明記されていない場合は「〜は米国版のみの仕様」と追記する
- 競合製品の仕様がソースと異なる場合（例: Apple Fitness+のApple Watch必須かどうか）は正確な情報に修正する
- タイトルや見出しに明確な誤字・誤表記がある場合は修正する（例: 「Leapord」→「reported」等）
"""

_QUALITY_SYSTEM = """\
あなたはTech Gear Guideの上級コピーエディターです。
記事の「面白さ・完読率・読者価値」を最大化することが専門です。
事実・数値・URLは変えずに、文章の品質だけを改善してください。
出力は必ず指定のMETAフォーマットで行ってください。
"""

_QUALITY_IMPROVE_PROMPT = """\
以下の記事の品質・エンゲージメントを改善してください。

【品質監査で指摘された問題】
{quality_issues}

【品質改善の原則（絶対に守ること）】
- 事実・数値・URL・引用元は一切変えない
- ソースにない情報を追加しない
- 上記の指摘問題を具体的に修正する

【改善の優先順位】
1. リード文（冒頭2〜3文）を書き直す場合:
   - 最初の1文に具体的な数値か驚きの事実を入れる
   - 「〜が発表されました」「〜が明らかになりました」の平凡な書き出しを避ける
   - 読者が「これは読む価値がある」と感じる具体性・意外性を入れる

2. 「So What?」が弱い段落を強化する:
   - 技術情報を「ユーザーが体感できる変化」に翻訳する
   - 「体感できるのは〜です」「日常的には〜という変化になります」等で補足する
   - 読者が「だから何？」と思う段落を残さない

3. 空虚フレーズを削除・置換する:
   - 「注目が集まっています」→ 具体的に誰が・なぜ注目しているかを書く、または削除
   - 「話題となっています」「期待が高まっています」→ 削除か具体表現に変換
   - 「業界関係者の間で」→ 削除か具体的な企業・人名に変換

4. 接続詞の多用を解消する:
   - 「なお、」「また、」「さらに、」を段落冒頭に多用している → 文章の流れで自然につなぐ
   - 接続詞なしで段落をつなげる、または文を統合する

5. FAQを実用的に書き直す:
   - 形式的な「現時点では〜確認されていません」だけのQAを書き直す
   - 読者が本当に知りたい疑問（買うべきか、いつ来るか、自分への影響は等）に答える

6. 見出しを魅力的にする:
   - 「〜について」「〜とは」という説明的な見出しを → 読者の関心に刺さる具体的な見出しに変える
   - 見出しを読むだけで記事の価値が伝わるようにする

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

同じ出力フォーマット（---META---〜---END_META---＋本文）で出力してください。
slug は絶対に変更しない。本文は最低 {min_len} 文字以上。
category は必ず以下の許容値のいずれかにすること: smartphone / windows / cpu_gpu / ai / tablet / xr / wearable / general
ソース記事のメタ情報（著者名・文字数・英語カテゴリ名・関連キーワード・記事URL等）が本文に含まれている場合は完全に削除すること。
タイトルで「N個/N点/Nつ/N選/Nポイント/N理由」と数を宣言しているのに本文で未列挙の場合は、本文に番号付きで列挙すること。
具体的な数値・固有名詞・専門家コメントは記事の信頼性と価値の源泉であり、抽象的な表現で済ませないこと。
"""

QUALITY_IMPROVE_THRESHOLD = 7  # このスコア未満は品質改善対象

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

_FUTURE_CONTEXT_RE = re.compile(
    r'(\d{4})年.{0,40}(?:発売|発表|リリース|公開|開催|登場|予定|実装)',
)
_CROSS_BATCH_RE    = re.compile(r'同日[にも].{0,40}(?:報じ|発表|リリース|公開|明らか)')
_INTERNAL_SCORE_RE = re.compile(r'\b[1-5]/5(?:と|で|に|は|の)')

def is_still_fail(
    body: str,
    title: str,
    slug: str,
    published_at: str = "",
) -> tuple[bool, list[str]]:
    """修正後の基本チェック（基本構造 + 重要精度チェック）"""
    fails = []
    if len(body) < MIN_BODY_LEN:
        fails.append(f"本文が短すぎます（{len(body)}文字）")
    if not title:
        fails.append("タイトルがありません")
    if not slug or not re.match(r'^[a-z0-9\-]+$', slug):
        fails.append(f"スラッグが不正: {slug}")

    # 修正後も年号ハルシネーションが残っていないか
    if published_at:
        try:
            from datetime import datetime as _dt
            pub_year = _dt.fromisoformat(published_at).year
            for m in _FUTURE_CONTEXT_RE.finditer(body):
                if int(m.group(1)) < pub_year:
                    ctx = body[m.start(): m.start() + 50].replace("\n", " ")
                    fails.append(f"修正後も年号ずれが残存: 「{ctx[:40]}」")
                    break
        except Exception:
            pass

    # 修正後もバッチ汚染が残っていないか
    if _CROSS_BATCH_RE.search(body):
        fails.append("修正後もバッチ間汚染パターン（同日に〜）が残存しています")

    # 修正後も内部スコアが残っていないか
    if _INTERNAL_SCORE_RE.search(body):
        fails.append("修正後も内部スコア（X/5）が本文に残存しています")

    return bool(fails), fails

# ─────────────────────────────────────────────
# 修正処理
# ─────────────────────────────────────────────

async def _call_claude(client, system, prompt, slug, label) -> Optional[str]:
    """Claude APIを呼び出してテキストを返す。失敗時はNone。"""
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        print(f"  ❌ {label}エラー（{slug}）: {e}")
        return None


async def correct_one(
    client: anthropic.AsyncAnthropic,
    article: dict,
    report: dict,
    source_map: dict,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        slug          = article.get("slug", "")
        status        = report.get("status", "PASS")
        quality_score = report.get("quality_score")
        quality_verdict = report.get("quality_verdict", "")
        quality_issues  = report.get("quality_issues", [])

        need_fact_fix    = status in ("WARN", "FAIL")
        need_quality_fix = (
            (quality_score is not None and quality_score < QUALITY_IMPROVE_THRESHOLD)
            or quality_verdict == "low"
        )

        if not need_fact_fix and not need_quality_fix:
            return article

        current = dict(article)
        # 前回実行で付いたフラグをリセット（再実行時の誤カウント・Phase2スキップを防ぐ）
        for _stale_key in ("_corrected", "_correction_failed", "_correction_skipped",
                           "_quality_improved", "_quality_improved_at", "_corrected_at"):
            current.pop(_stale_key, None)
        tags_str = ", ".join(article.get("tags", []))

        # ── Phase 1: 事実修正 ──────────────────────────────────
        if need_fact_fix:
            all_issues = report.get("issues", []) + report.get("warnings", [])
            if all_issues:
                source_urls   = [s.get("url", "") for s in article.get("sources", [])]
                source_bodies = [source_map[u] for u in source_urls if u in source_map]

                if not source_bodies:
                    print(f"  ⚠️  ソースなし（事実修正スキップ）: {slug}")
                    current["_correction_skipped"] = True
                else:
                    prompt = _FACT_CORRECT_PROMPT.format(
                        issues="\n".join(f"- {i}" for i in all_issues),
                        source_body=source_bodies[0][:3500],
                        title=current.get("title", ""),
                        slug=slug,
                        category=current.get("category", ""),
                        tags=tags_str,
                        article_type=current.get("article_type", "A型速報"),
                        seo_description=current.get("seo_description", ""),
                        body=current.get("body", "")[:4000],
                        min_len=MIN_BODY_LEN,
                    )
                    text = await _call_claude(client, _FACT_SYSTEM, prompt, slug, "事実修正")
                    if text:
                        meta = parse_meta(text)
                        body = extract_body(text)
                        if meta.get("title") and len(body) >= 800:
                            current["body"]            = body
                            current["title"]           = meta.get("title", current["title"])
                            current["seo_description"] = meta.get("seo_description", current.get("seo_description", ""))
                            if meta.get("tags"):
                                current["tags"] = parse_tags(meta["tags"])
                            # categoryを修正（不正カテゴリはfallback）
                            new_cat = meta.get("category", "").strip()
                            if new_cat in VALID_CATEGORIES:
                                current["category"] = new_cat
                            elif current.get("category") not in VALID_CATEGORIES:
                                current["category"] = "general"
                            current["_corrected"]    = True
                            current["_corrected_at"] = datetime.now(timezone.utc).isoformat()
                            print(f"  ✅ 事実修正完了 [{status}]: {slug}")
                        else:
                            print(f"  ⚠️  事実修正出力が不十分（本文{len(body)}字）: {slug}")
                            current["_correction_failed"] = True
                    else:
                        current["_correction_failed"] = True

        # ── Phase 2: 品質改善 ──────────────────────────────────
        if need_quality_fix and not current.get("_correction_failed"):
            issues_text = "\n".join(f"- {i}" for i in quality_issues) if quality_issues else "（詳細なし）"
            score_label = f"{quality_score}/10" if quality_score is not None else quality_verdict
            prompt = _QUALITY_IMPROVE_PROMPT.format(
                quality_issues=f"品質スコア: {score_label}\n{issues_text}",
                title=current.get("title", ""),
                slug=slug,
                category=current.get("category", ""),
                tags=tags_str,
                article_type=current.get("article_type", "A型速報"),
                seo_description=current.get("seo_description", ""),
                body=current.get("body", "")[:4000],
                min_len=MIN_BODY_LEN,
            )
            text = await _call_claude(client, _QUALITY_SYSTEM, prompt, slug, "品質改善")
            if text:
                meta = parse_meta(text)
                body = extract_body(text)
                if meta.get("title") and len(body) >= 800:
                    current["body"]            = body
                    current["title"]           = meta.get("title", current["title"])
                    current["seo_description"] = meta.get("seo_description", current.get("seo_description", ""))
                    if meta.get("tags"):
                        current["tags"] = parse_tags(meta["tags"])
                    new_cat = meta.get("category", "").strip()
                    if new_cat in VALID_CATEGORIES:
                        current["category"] = new_cat
                    elif current.get("category") not in VALID_CATEGORIES:
                        current["category"] = "general"
                    current["_quality_improved"]    = True
                    current["_quality_improved_at"] = datetime.now(timezone.utc).isoformat()
                    print(f"  ✅ 品質改善完了 [スコア{score_label}]: {slug}")
                else:
                    print(f"  ⚠️  品質改善出力が不十分（本文{len(body)}字）: {slug}")

        return current

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

    def needs_work(article: dict) -> bool:
        r = reports.get(article.get("slug", ""), {})
        if r.get("status") in ("WARN", "FAIL"):
            return True
        qs = r.get("quality_score")
        if qs is not None and qs < QUALITY_IMPROVE_THRESHOLD:
            return True
        if r.get("quality_verdict") == "low":
            return True
        return False

    need_correction = [a for a in articles if needs_work(a)]
    pass_articles   = [a for a in articles if not needs_work(a)]

    fact_fix_count    = sum(1 for a in articles if reports.get(a.get("slug",""),{}).get("status") in ("WARN","FAIL"))
    quality_fix_count = sum(
        1 for a in articles
        if (reports.get(a.get("slug",""),{}).get("quality_score") or 10) < QUALITY_IMPROVE_THRESHOLD
        or reports.get(a.get("slug",""),{}).get("quality_verdict") == "low"
    )
    print(f"事実修正対象: {fact_fix_count} 件 / 品質改善対象: {quality_fix_count} 件 / スキップ: {len(pass_articles)} 件")

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
        slug         = a.get("slug", "")
        body         = a.get("body", "")
        title        = a.get("title", "")
        published_at = a.get("published_at", "")
        fail, reasons = is_still_fail(body, title, slug, published_at)
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

    fact_corrected  = sum(1 for a in corrected_list if a.get("_corrected"))
    quality_improved = sum(1 for a in corrected_list if a.get("_quality_improved"))
    skipped_count   = sum(1 for a in corrected_list if a.get("_correction_skipped"))
    failed_count    = sum(1 for a in corrected_list if a.get("_correction_failed"))

    print("\n── 修正結果 ──")
    print(f"  ✅ 事実修正成功  : {fact_corrected} 件")
    print(f"  ✅ 品質改善成功  : {quality_improved} 件")
    print(f"  ⚠️  ソースなしスキップ: {skipped_count} 件")
    print(f"  ❌ 修正失敗      : {failed_count} 件")
    print(f"  ❌ 最終FAIL除外  : {excluded} 件")
    print(f"  → publish.py に渡す件数: {len(final_articles)} 件")


if __name__ == "__main__":
    asyncio.run(main())
