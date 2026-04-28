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
import os
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

# H2見出しパターン
_H2_RE = re.compile(r'^## .+', re.MULTILINE)

# 常套句締め文句（AI感が出やすいパターン）
_CLICHE_ENDING_PATTERNS = [
    r'続報を待ちましょう',
    r'続報をお待ちください',
    r'続報を待つのが(?:妥当|正解|賢明)',
    r'続報が出た段階で',
    r'現時点では続報を',
    r'今後の動向に注目',
    r'引き続き注目して',
]
_CLICHE_ENDING_RE = re.compile('|'.join(_CLICHE_ENDING_PATTERNS))

# タイトルに使ってはいけない確定表現（リーク・未確認記事）
_TITLE_DEFINITIVE_RE = re.compile(
    r'(?:判明|確定|決定|明らか|確認|正式|事実|確証)'
)
# タイトルの煽り語句
_TITLE_HYPE_RE = re.compile(
    r'(?:大変身|激変|崩壊|革命|終焉|衝撃|驚異|塗り替え|覆す|完全否定|ガチ|やばい|リセット)'
)

# 極端な%数値（1000%以上）
_EXTREME_PCT_RE = re.compile(r'(\d{4,})%')

# 単一原因への過帰属パターン
_SINGLE_CAUSE_RE = re.compile(
    r'(?:のみが原因|だけが理由|だけで(?:利益|改善|達成|実現)|のみによって|だけに(?:よる|起因))'
)

# ダミー機・APK・Telegram等の情報源キーワード（記事内で明記されているかチェック用）
_LEAK_SOURCE_KEYWORDS = ["ダミー機", "APK", "Telegram", "テレグラム", "モックアップ", "mock"]

# 企業向け機能の一般化危険パターン
_ENTERPRISE_GENERAL_RE = re.compile(
    r'(?:誰でも|ユーザーなら誰でも|一般ユーザーも).{0,30}(?:削除|無効化|ブロック|制限|設定)'
)

# 内部スコア混入パターン
_INTERNAL_SCORE_RE = re.compile(r'\b[1-5]/5(?:と|で|に|は|の)')
_STAR_RATING_RE    = re.compile(r'[★☆]{3,}')

# ソース記事メタ情報の混入パターン（著者・文字数・カテゴリ・関連KW等）
_SOURCE_META_AUTHOR_RE = re.compile(
    r'(?:著者|執筆者|Author)[：:]\s*\S+|'
    r'(?:[A-Z][a-z]+\s+[A-Z][a-z]+)氏[（(][A-Za-z0-9 &]+[）)]',  # 「Brady Snyder氏（Android Authority）」
)
_SOURCE_META_WORDCOUNT_RE = re.compile(
    r'(?:記事の)?文字数[：:]\s*約?\d|'
    r'約\d[\d,]+語[（(]英語[）)]',  # 「約1,338語（英語）」
)
_SOURCE_META_CATEGORY_RE = re.compile(
    r'カテゴリ[：:]\s*(?:Features|News|Reviews|Deals|Opinion)',  # 英語カテゴリ名
)
_SOURCE_META_KEYWORDS_RE = re.compile(
    r'関連キーワード[：:]\s*\S',  # 「関連キーワード: Google、...」
)
_SOURCE_META_ARTICLEURL_RE = re.compile(
    r'記事URL[：:]\s*https?://'  # 「記事URL: https://...」
)

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
    """内部スコア・星表示・ソース記事メタ情報が本文に混入していないか検出"""
    issues: list[str] = []
    if _INTERNAL_SCORE_RE.search(body):
        issues.append("内部ソーススコア（X/5）が本文に混入している可能性があります")
    if _STAR_RATING_RE.search(body):
        issues.append("信頼度星表示（★☆×3以上）が本文に残っている可能性があります")
    # ソース記事のメタ情報混入チェック
    if _SOURCE_META_AUTHOR_RE.search(body):
        issues.append("ソース記事の著者情報（氏名・媒体名）が本文に混入しています（記載厳禁）")
    if _SOURCE_META_WORDCOUNT_RE.search(body):
        issues.append("ソース記事の文字数情報が本文に混入しています（記載厳禁）")
    if _SOURCE_META_CATEGORY_RE.search(body):
        issues.append("ソース記事の英語カテゴリ名（Features等）が本文に混入しています（記載厳禁）")
    if _SOURCE_META_KEYWORDS_RE.search(body):
        issues.append("ソース記事の「関連キーワード:」フィールドが本文に混入しています（記載厳禁）")
    if _SOURCE_META_ARTICLEURL_RE.search(body):
        issues.append("「記事URL:」という形式でソースURLが本文に混入しています（記載厳禁）")
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

def check_title_accuracy(title: str, article: dict) -> list[str]:
    """タイトルの確定表現・煽り語句をチェック"""
    warnings = []
    article_type = article.get("article_type", "")
    body         = article.get("body", "")

    # リーク・噂系記事で「判明」等の確定表現が使われていないか
    is_uncertain = (
        article_type == "C型リーク"
        or any(h in body for h in ["リーク", "噂", "ダミー機", "APK", "未確認"])
    )
    if is_uncertain and _TITLE_DEFINITIVE_RE.search(title):
        m = _TITLE_DEFINITIVE_RE.search(title)
        warnings.append(
            f"タイトルに「{m.group()}」がありますが、未確認情報の記事では"
            "「可能性」「示唆」「か」等の表現が正確です"
        )

    if _TITLE_HYPE_RE.search(title):
        m = _TITLE_HYPE_RE.search(title)
        warnings.append(f"タイトルに煽り語句「{m.group()}」があります。読者の期待を超えた表現になっていないか確認してください")

    return warnings

def check_h2_count(body: str) -> list[str]:
    """H2見出し数が仕様範囲（3〜5個）かチェック"""
    count = len(_H2_RE.findall(body))
    if count < 3:
        return [f"H2見出しが少なすぎます（{count}個、最低3個必要）"]
    if count > 5:
        return [f"H2見出しが多すぎます（{count}個、最大5個推奨）"]
    return []

def check_source_urls(article: dict) -> list[str]:
    """出典リストにURLが存在するか確認"""
    sources = article.get("sources", [])
    if not sources:
        return ["出典が1件もありません"]
    missing = [
        s.get("title", "（タイトルなし）")
        for s in sources
        if not s.get("url", "").startswith("http")
    ]
    if missing:
        return [f"出典URLが欠落しています: {', '.join(missing[:2])}"]
    return []

def check_cliched_endings(body: str) -> list[str]:
    """AI感が出やすい定型締め文句の多用を検出"""
    matches = _CLICHE_ENDING_RE.findall(body)
    if len(matches) >= 2:
        return [f"常套句の締め文句が{len(matches)}箇所あります（AI生成感につながります）: 「{matches[0]}」等"]
    return []

def check_extreme_percentage(body: str) -> list[str]:
    """1000%以上の極端な%表示を検出（誤解を招く可能性）"""
    warnings = []
    for m in _EXTREME_PCT_RE.finditer(body):
        pct = int(m.group(1))
        if pct >= 1000:
            warnings.append(
                f"極端な%表示「{pct}%」があります。"
                "絶対値（例: 予想0.01ドルに対し0.29ドル）での表現を検討してください"
            )
    return warnings[:2]

def check_single_cause_overattribution(body: str) -> list[str]:
    """単一原因への過度な帰属を検出"""
    if _SINGLE_CAUSE_RE.search(body):
        m = _SINGLE_CAUSE_RE.search(body)
        ctx = body[max(0, m.start()-20): m.end()+20].replace("\n", " ")
        return [f"単一原因への過帰属の疑い: 「{ctx[:60]}」（ソースが複数要因を挙げている場合は要確認）"]
    return []

def check_leak_source_clarity(article: dict) -> list[str]:
    """ダミー機・APK解析・Telegram等の記事で、情報源の種類が本文内に明記されているか"""
    warnings = []
    body = article.get("body", "")
    title = article.get("title", "")
    text  = title + body

    found_keyword = any(kw.lower() in text.lower() for kw in _LEAK_SOURCE_KEYWORDS)
    if not found_keyword:
        return []

    # キーワードはあるが、情報源の限界（最終製品と異なる可能性）に触れていない
    limitation_phrases = ["最終製品", "確定ではない", "変わる可能性", "未発表", "公式仕様ではない"]
    has_limitation = any(p in body for p in limitation_phrases)
    if not has_limitation:
        warnings.append(
            "ダミー機・APK解析等の情報源を使用していますが、"
            "「最終製品の仕様は変わる可能性があります」等の限界の明示がありません"
        )
    return warnings

def check_enterprise_feature_generalization(body: str, source_bodies: list[str]) -> list[str]:
    """企業向け・管理者向け機能を一般ユーザー向けとして書いていないか"""
    warnings = []
    source_text = " ".join(source_bodies).lower()
    # ソースにenterprise/managed/admin向けの言及がある
    is_enterprise_src = any(
        kw in source_text
        for kw in ["managed device", "enterprise", "admin", "policy", "group policy", "mdm"]
    )
    if is_enterprise_src and _ENTERPRISE_GENERAL_RE.search(body):
        warnings.append(
            "ソースでは企業・管理者向けの機能として説明されていますが、"
            "記事では一般ユーザー向けとして書かれている可能性があります"
        )
    return warnings

def check_article_type_rules(article: dict) -> list[str]:
    """記事タイプ別の必須要件チェック"""
    issues = []
    article_type = article.get("article_type", "")
    sources      = article.get("sources", [])

    if article_type == "C型リーク":
        reliability = article.get("source_reliability", 0)
        if not reliability or reliability == 0:
            issues.append("C型リーク記事はsource_reliabilityの設定が必須です")

    if article_type == "B型深掘り" and len(sources) < 2:
        issues.append(f"B型深掘り記事はソースが2件以上推奨です（現在{len(sources)}件）")

    return issues

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

11.【ソース外の独自主張・過剰補足】
    - ソースに書かれていない「背景説明」「業界解説」「日本市場への影響」が、
      あたかも事実のように断定されていないか
    - ソースの情報だけでは導けない結論をAIが独自に追加していないか

12.【主語・範囲の不正確な拡大】
    - ソースが「A機能」について言及しているのに、記事で「製品全体」「製品ライン全体」「業界全体」に拡大していないか
    - 例: 「スタートメニューが60%高速化」→「Windows 11のUIが60%高速化」への拡大は不正確
    - 例: 「Proモデルが12GB RAM」→「ラインナップ全体が12GB RAM」への拡大は不正確

13.【情報源の伝達経路の正確な表記】
    - ソースAがソースBを引用している場合（例: Neowin via Windows Central）、
      記事で帰属先が正確に書かれているか
    - 「Neowinが伝えた」だけでなく「Windows Centralの報告をNeowinが引用」という
      構造が必要な場合に省略されていないか
    - APK解析・内部テスト・リーク画像などの情報源の種類（一次情報かどうか）が
      記事内で読者に伝わるか

14.【ネガティブ情報・リスク・逆風の省略】
    - ソースがリスク（risks/headwinds/challenges/concerns）や課題を言及しているのに、
      記事でポジティブな情報だけを取り上げて省略していないか
    - 例: Intel決算でCFOが「PC市場の弱さ・18A立ち上げコスト・材料費上昇」を
      挙げているのに、「需要は衰えていない」とだけ書く
    - ネガティブ情報を無視してバランスを失っている記事は正確性が下がる

15.【対立する情報・相反するリークの省略】
    - 同じトピックで複数の相反する情報が存在する場合、片方だけ引用していないか
    - 例: ダミー機では本体厚8.75mmだが、別リークでは8.8mmという説もある、など
    - ソース内で「一方で別の情報源は〜と報じている」という記述がある場合、
      記事でその対立が読者に伝わるか

16.【企業向け・管理者向け機能の一般化】
    - ソースで「managed devices」「enterprise」「admin policy」向けの機能として
      説明されているものを、一般ユーザーも使える機能として書いていないか
    - 例: Copilot削除機能がMDM管理デバイス向けなのに「誰でも削除できる」と書く

17.【複数要因の単一要因への過度な単純化】
    - ソースが複数の要因（A・B・Cが複合した結果）と説明しているのに、
      記事がAだけが原因のように書いていないか
    - 例: Intel粗利改善は「在庫販売」「販売量」「価格」「製品ミックス」「歩留まり改善」
      の複合だが、「在庫を捨てずに売ったから」だけに帰属させる

18.【情報源の階層の混同 ★重要】
    - ソース記事がメディア（Tom's Hardware・TechRadar等）である場合、
      そのメディアが企業公式発表を「解釈・推定・計算」した内容を、
      あたかも「企業が直接述べた」かのように記事が断定していないか
    - 例: Tom's HardwareがTSMCロードマップを元に「48倍」と計算したのを、
      「TSMCは48倍になると述べた」と書くのは不正確
    - 例: TechRadarがCarnivalの対応を「supply-chain breach」と表現したのを、
      「カーニバル社がサプライチェーン攻撃として認めた」と書くのは不正確
    - 正しい書き方: 「Tom's Hardwareは、TSMCロードマップを基に〜と報じている」
                    「TechRadarは〜とカーニバル社の対応を報じている」

19.【数量単位の誤変換】
    - ソースが「records」「entries」（レコード件数）と表現しているデータを、
      記事で「顧客数」「ユーザー数」「人数」として書いていないか
    - 例: ソースが「8.7 million records」なのに「875万人の顧客が漏洩」は誤り
    - 1件のレコードが1人の顧客を意味しない場合があるため、
      単位はソース通りに「○○件のレコード」と書くべき

20.【メディア評価語の事実断定化】
    - ソース記事（メディア）が自分の解釈・評価として書いた語句を、
      記事が事実として断定的に使っていないか
    - 例: TechRadarが「大幅に矮小化した」という評価を書いているのを、
      記事が「カーニバル社は大幅に矮小化した」と事実のように断定するのは危険
    - 評価語（矮小化・過小評価・隠蔽・完全否定等）は、
      必ず「（メディア名）は〜と報じている」という形で帰属を明示すべき

21.【アナリスト・リーク情報源の断定化 ★重要】
    - ソースがアナリスト観測・サプライチェーン情報・匿名情報源に基づく記事の場合、
      記事が「開発中」「参加」「確定」等の断定形を使っていないか
    - 正しい帰属: 「Ming-Chi Kuo氏は〜と主張した」「〜と報じられている」「〜の可能性があるとされる」
    - NG: 「OpenAIがMediaTekとチップを開発中」（公式確認なしに断定）
    - OK: 「Kuo氏によると、OpenAIがMediaTekとチップを開発している可能性があるとされる」
    - OpenAI・Qualcomm・MediaTek・Luxshare等が公式にコメントしていない場合は必ず「未確認」と書くべき

22.【タイトル・リードの主張強度過剰 ★重要】
    - ソースが「可能性」「示唆」「観測」のレベルなのに、タイトル・リードが断定的でないか
    - NG: 「アイコンが消える日——OpenAIが2028年量産目標のスマートフォンを開発中」
    - OK: 「OpenAIがAIエージェント中心のスマホを検討か——Kuo氏が2028年量産・Luxshare関与を報告」
    - NG: 「安いのに上位機に勝つ」（条件なしの断定）
    - OK: 「実用面4点でPixel 10aが優位——Android Authorityが指摘」
    - タイトルのキャッチコピーがソースの主張強度を超えている場合は major_issues として報告すること

23.【条件付き優位性の無条件化 ★重要】
    - ソースが「X点でAがBを上回る」と言っているのに、記事が無条件に「AはBより優れる」と書いていないか
    - 例: レビュアーが「4点の実用面でPixel 10aが優位」と言っているのに「Pixel 10を超える」と書く
    - 総合評価・性能全体の比較ではなく、特定観点での優位であることを明示すること

24.【レビュアー主観の事実化 ★重要】
    - ソースがレビュー・比較記事（Features/Review）の場合、
      レビュアーの評価・感想・主観が事実として記述されていないか
    - NG: 「実機で証明された」（定量測定・実験でなければ使えない語）
    - OK: 「Brady Snyder氏は〜と評価している」「レビュアーは〜と述べている」
    - 「証明」「実証」という語は、定量的な実験・測定がソースに存在する場合のみ使う

25.【絶対語の誇張 ★重要】
    - 「ゼロにする」「完全に解決」「すべてのストレスを排除」等の絶対語がソース根拠なしに使われていないか
    - NG: 「アプリ切り替えストレスをゼロにする」（ソースにない表現）
    - OK: 「アプリ切り替えの手間を大幅に削減できる」
    - NG: 「完全に無料で使える」（無料範囲が限定的な場合）
    - OK: 「一部のコンテンツは無料で利用できる」

26.【ビジネス戦略・意図の推測の断定化】
    - 企業が明言していない戦略・意図を記事が事実のように書いていないか
    - NG: 「無料層を囲い込み、Premium課金へ誘導する狙いがある」（Spotifyが明言していない）
    - OK: 「無料層の取り込みと有料転換の両立を狙っていると読める」
    - 推測には必ず「と読める」「との見方もある」「と考えられる」を付けること

27.【ソースにない詳細説明・仕組み解説の追加】
    - ソースに書かれていない技術仕組み・背景説明・役割分担の推測が追加されていないか
    - NG: 「MediaTekがミドルレンジ、QualcommがハイエンドSoCを担当する可能性がある」（ソースにない）
    - NG: Q&Aで「詳細はメタデータにない」と書きながら、本文で詳細説明を展開している矛盾
    - ソースにない詳細は一切追加せず、「詳細は出典元を参照」と誘導すること

28.【タイトルで宣言した数と本文の列挙が一致しているか ★最重要】
    - タイトル・リードに「N個」「N点」「Nつ」「N選」「Nポイント」「N理由」等が含まれる場合、
      本文でその数だけの内容を箇条書き・番号リスト・H2見出しで明示しているか
    - NG: 「4つのポイントを実機で評価」というタイトルなのに本文でポイントを列挙していない
    - OK: タイトルで「4つ」と宣言 → 本文に①〜④または「① フラット背面デザイン」等で4点明示
    - これが守られていない場合は major_issues として報告すること

29.【ソースの具体情報（数値・固有名詞・コメント）の引き継ぎ ★重要】
    - ソース記事にある具体的な数値（重量・バッテリー容量・スペック・価格）が記事に含まれているか
    - NG: Pixel 10aが183g、Pixel 10が204gという具体値がソースにあるのに記事が「軽量化されている」とだけ書く
    - OK: 「Pixel 10aは183gで、Pixel 10（204g）より21g軽くなっています」
    - NG: バッテリー5,100mAh vs 4,970mAhという数値がソースにあるのに記事に数値がない
    - 専門家・レビュアーのコメントがソースにある場合は（媒体名）として引用すること

30.【競合・比較対象の仕様が最新・正確か ★重要】
    - 比較記事で競合製品（Apple・Google・Samsung等）の仕様を述べる場合、その情報が正確か
    - 特に注意: 「Apple Fitness+はApple Watch必須」は現在は誤り（iPhone単体で利用可能）
    - ソースが古い情報で競合を説明している場合は「ソース記事では〜と記載されているが現行仕様と異なる可能性がある」と注記すべき
    - 地域限定仕様（米国版のみ等）がソースにある場合、記事でも地域限定であることを明記しているか

31.【見出し・タイトルの誤字・表記誤り ★最重要】
    - タイトルや見出しに明確な誤字・誤表記がないか（例: 「アナリストがLeapord」のような誤字）
    - 英語の固有名詞・ブランド名の表記が正しいか
    - 誤字は minor_issues ではなく major_issues として報告すること

JSON形式のみで回答（コードブロック不要）:
{{"verdict": "accurate"|"minor_issues"|"major_issues", "issues": ["具体的な問題（例: ソースは2026年7月発売と書いているが記事では2025年7月22日と誤記）"], "confidence": 0.0-1.0}}

【ソース記事】
{source_body}

【生成記事（公開日: {published_at}）】
{article_body}
"""

# ─────────────────────────────────────────────
# Pass 2: 品質・エンゲージメント監査
# ─────────────────────────────────────────────

# 空虚フレーズ（AI生成感・情報ゼロの常套句）
_EMPTY_PHRASE_PATTERNS = [
    (r'注目が集まっています',       "注目フレーズ"),
    (r'話題(?:と|に)なっています',  "話題フレーズ"),
    (r'大きな注目を集め',           "注目フレーズ"),
    (r'世界中で話題',               "誇大フレーズ"),
    (r'業界関係者の間で',           "曖昧フレーズ"),
    (r'多くのユーザーが期待',       "曖昧フレーズ"),
    (r'今後の展開が注目され',       "展開フレーズ"),
    (r'ますます注目されて',         "注目フレーズ"),
    (r'引き続き注目したい',         "展開フレーズ"),
    (r'期待が高まっています',       "期待フレーズ"),
    (r'様々な(?:面|観点|側面)から', "曖昧フレーズ"),
]

# 接続詞の多用チェック（AI感）
_CONNECTOR_RE = re.compile(r'(?:^|\n)(?:なお、|また、|さらに、|一方で、)', re.MULTILINE)

def check_empty_phrases(body: str) -> list[str]:
    """情報を持たない空虚フレーズの多用を検出"""
    found = []
    for pat, label in _EMPTY_PHRASE_PATTERNS:
        if re.search(pat, body):
            found.append(label)
    if len(found) >= 2:
        return [f"空虚フレーズが{len(found)}種類あります（{', '.join(found[:3])}）。読者に実質的な情報がない表現を避けてください"]
    return []

def check_lead_quality(body: str) -> list[str]:
    """リード文（冒頭250字）に具体的な数値・固有名詞・驚きの事実があるか"""
    lead = body[:250]
    has_number  = bool(re.search(r'\d+', lead))
    has_proper  = bool(re.search(r'[A-Z][a-zA-Z]+|iPhone|Galaxy|Windows|Google|Apple|Intel|NVIDIA|AMD', lead))
    has_hook    = bool(re.search(r'(?:明らか|発覚|判明|報告|リーク|流出|初めて|史上|最大|最小|最高|最安|初搭載)', lead))
    if not (has_number or has_proper or has_hook):
        return ["リード文（冒頭）に具体的な数値・固有名詞・フックとなる事実がありません。最初の1文で読者を引き込む具体的な情報を入れてください"]
    return []

def check_connector_overuse(body: str) -> list[str]:
    """「なお、」「また、」「さらに、」の多用（AI感の原因）を検出"""
    count = len(_CONNECTOR_RE.findall(body))
    if count >= 6:
        return [f"接続詞（なお、また、さらに）が{count}回あります（AI感が出やすい）。文章の流れで自然につなぐか、削除を検討してください"]
    return []

# ── フィードバック由来の追加チェック ────────────────

# 企業が「認めた」「公式に発表した」と断定される危険パターン
_ENTITY_ADMITTED_RE = re.compile(
    r'(?:(?:Apple|Google|Microsoft|Samsung|Intel|AMD|TSMC|Meta|Amazon|Sony|NVIDIA|[A-Z][a-z]+(?:社|Corp|Inc|Ltd))'
    r'.{0,20}(?:認めた|認めています|公式に(?:発表|認|確認)|正式に(?:発表|認)|明言した|明言しています|'
    r'確認した|確認しています|示した|示しています))'
)

# 評価・解釈語（メディアの見解であることを示す語句）
_MEDIA_EVAL_WORDS = [
    "矮小化", "過小評価", "隠蔽", "大幅に下回る", "著しく誇張",
    "完全に否定", "全面的に認めた", "事実上の撤退", "事実上の敗北",
    "デマ", "プロパガンダ",
]
_MEDIA_EVAL_RE = re.compile('|'.join(re.escape(w) for w in _MEDIA_EVAL_WORDS))

# 「records」「件のレコード」を「人」「顧客」「ユーザー」に言い換える誤変換
_RECORD_COUNT_RE = re.compile(
    r'(\d[\d,万]+)\s*(?:件の|万人の|万件の)?(?:顧客|ユーザー|利用者|被害者|会員|人).{0,20}(?:漏洩|流出|影響|盗|被害)',
)
_RECORD_SOURCE_RE = re.compile(
    r'\b(\d[\d,]+)\s*(?:million|billion)?\s*(?:records|entries|rows|data points)\b',
    re.IGNORECASE,
)


def check_source_attribution_hierarchy(body: str, source_bodies: list[str]) -> list[str]:
    """
    ソースメディアの解釈・推定を、元の企業・機関の発言として書いていないかチェック。
    例: Tom's HardwareがTSMCロードマップを「解釈して48倍」と書いたのを
        「TSMCは48倍になると述べた」と断定するケース。
    """
    warnings = []
    if not source_bodies:
        return warnings

    # ソースがメディア記事（企業公式PRではない）かつ、
    # 記事内で企業を主語にした「述べた」「発表した」系の断定がある場合
    source_text = " ".join(source_bodies)
    is_media_source = any(
        domain in source_text.lower()
        for domain in ["tomshardware", "techradar", "wccftech", "notebookcheck",
                       "androidauthority", "9to5", "macrumors", "theverge",
                       "gsmarena", "neowin", "windowscentral", "androidpolice"]
    )
    if not is_media_source:
        return warnings

    # 企業が「述べた」「発表した」系の断定が記事にある
    admitted_m = _ENTITY_ADMITTED_RE.search(body)
    if admitted_m:
        ctx = body[max(0, admitted_m.start()-10): admitted_m.end()+30].replace("\n", " ")
        warnings.append(
            f"情報源の階層に注意: 「{ctx[:70]}」— "
            "ソースはメディア記事であり、企業の公式発表として断定するには根拠が弱い可能性があります。"
            "「（メディア名）は〜と報じている」と書くことを検討してください"
        )

    return warnings


def check_media_evaluation_words(body: str, source_bodies: list[str]) -> list[str]:
    """
    「矮小化」「隠蔽」等のメディアの評価・解釈語が、
    事実として断定的に記述されていないかチェック。
    """
    warnings = []
    m = _MEDIA_EVAL_RE.search(body)
    if not m:
        return warnings

    eval_word = m.group()
    # ソース本文にその評価語（英語含む）が含まれているか
    source_text = " ".join(source_bodies).lower()
    source_has_it = eval_word in source_text or any(
        eng in source_text for eng in ["downplayed", "minimized", "concealed", "suppressed"]
    )

    # 記事内でメディア帰属（「と○○は報じている」等）が付いているか
    vicinity = body[max(0, m.start()-60): m.end()+60]
    has_attribution = bool(re.search(
        r'(?:と|として|と伝え|と報じ|によると|によれば).{0,20}(?:報じ|伝え|指摘|述べ)',
        vicinity,
    ))

    if not has_attribution:
        warnings.append(
            f"評価語「{eval_word}」が事実として断定されています。"
            "これはメディア側の解釈・評価である可能性があるため、"
            "「（メディア名）は〜と報じている」と帰属を明示してください"
        )

    return warnings


def check_unit_conflation(body: str, source_bodies: list[str]) -> list[str]:
    """
    数量の単位誤変換を検出。
    「records/entries」（レコード件数）を「顧客数/ユーザー数/人数」に誤変換するケース。
    例: 「8.7 million records」→「875万人の顧客が漏洩」
    """
    warnings = []
    source_text = " ".join(source_bodies)

    # ソースに「records」「entries」系の表現がある
    rec_m = _RECORD_SOURCE_RE.search(source_text)
    if not rec_m:
        return warnings

    # 記事で「○○人/顧客/ユーザー」として書いている
    art_m = _RECORD_COUNT_RE.search(body)
    if art_m:
        warnings.append(
            f"単位の誤変換の疑い: ソースでは「records/entries」（レコード件数）と"
            f"表現されているデータを、記事では「{art_m.group()[:40]}」と"
            "人数・顧客数として書いています。"
            "1件のレコードが1人の顧客を意味しない場合があるため、"
            "「○○件のレコード」と書くことを推奨します"
        )

    return warnings

# ── フィードバック第2弾：誇張・拡大解釈パターン ────────────

# アナリスト・リーク情報源を示すキーワード
_ANALYST_SOURCE_WORDS = [
    "アナリスト", "Kuo", "クオ", "観測", "サプライチェーン", "リーク",
    "匿名情報源", "信頼できる情報源", "trusted source", "supply chain",
    "関係者によると", "報じられている", "と伝えられる",
]

# 断定語（アナリスト情報源でこれらが使われると誇張）
_ASSERTION_RE = re.compile(
    r'(?:開発中|製造中|参加(?:する|している|した)|'
    r'確認され|発売(?:する|される|した)|量産(?:する|される|した)|'
    r'(?:正式に|公式に)(?:発表|確認|決定|採用)|'
    r'採用(?:される|された|が決まった))',
)

# 比較優位を示す無条件表現
_BEATS_RE = re.compile(
    r'(?:上位機?に勝つ|上位機?を超える?|上位機?より優れる?|'
    r'全面的に上回る|総合的に勝る|圧倒的に上回る|'
    r'明らかに優れている|すべての点で)',
)

# 絶対語（ソース根拠なしで使うと誇張）
_ABSOLUTE_WORDS_RE = re.compile(
    r'(?:ゼロにする|完全に(?:解決|消える?|なくなる?|排除)|'
    r'実機で証明|科学的に証明|確実に|間違いなく|'
    r'すべての(?:問題|課題|ストレス)|絶対に(?!変更しない|に記載しない))',
)

# ビジネス戦略の推測で帰属なし
_STRATEGY_INFERENCE_RE = re.compile(
    r'(?:狙いがある|狙いが(?:見える|透ける)|戦略(?:だ|である)|'
    r'意図(?:がある|が見える)|計算された|仕組みだ|'
    r'シナリオ(?:だ|である|として))',
)


def check_analyst_claim_attribution(body: str, article: dict) -> list[str]:
    """
    アナリスト・リーク情報源の主張が、帰属表現なく断定されていないかチェック。
    例: 「開発中」「参加」などの断定形が、アナリスト観測記事で使われるケース。
    """
    warnings = []
    sources = article.get("sources", [])
    source_titles = " ".join(s.get("title", "") + " " + s.get("url", "") for s in sources).lower()

    # ソースにアナリスト・リーク由来の記事が含まれているか
    has_analyst_source = any(
        kw.lower() in source_titles or kw.lower() in body.lower()
        for kw in _ANALYST_SOURCE_WORDS
    )
    if not has_analyst_source:
        return warnings

    # 断定語が帰属表現なしで出現しているか
    for m in _ASSERTION_RE.finditer(body):
        vicinity = body[max(0, m.start() - 80): m.end() + 20]
        has_attribution = bool(re.search(
            r'(?:氏は|氏が|氏によると|によると|によれば|と報じ|と主張|と述べ|'
            r'とされ|と伝え|の観測では|の主張では|と(?:報告|予測|指摘))',
            vicinity,
        ))
        if not has_attribution:
            ctx = body[max(0, m.start() - 20): m.end() + 30].replace("\n", " ")
            warnings.append(
                f"誇張の疑い: 「{ctx[:60]}」— アナリスト観測情報が事実として断定されています。"
                "「○○氏によると」「〜と報じられている」等の帰属表現を付けてください"
            )
            break  # 1件だけ報告
    return warnings


def check_conditional_superiority(body: str, source_bodies: list[str]) -> list[str]:
    """
    比較優位表現が無条件・総合的な形で書かれていないかチェック。
    ソースが「X点で上回る」と言っているのに「上位機に勝つ」と無条件化するパターン。
    """
    warnings = []
    m = _BEATS_RE.search(body)
    if not m:
        return warnings

    ctx = body[max(0, m.start() - 30): m.end() + 50].replace("\n", " ")
    warnings.append(
        f"無条件優位表現の疑い: 「{ctx[:80]}」— "
        "ソースが特定の条件下での優位を述べている場合、"
        "「○点で上回る」「実用面では優位な部分もある」等、条件を明示してください"
    )
    return warnings


def check_absolute_words(body: str, source_bodies: list[str]) -> list[str]:
    """
    「ゼロ」「完全に」「実機で証明」等の絶対語がソース根拠なしで使われていないかチェック。
    """
    warnings = []
    m = _ABSOLUTE_WORDS_RE.search(body)
    if not m:
        return warnings

    source_text = " ".join(source_bodies).lower()
    absolute_word = m.group()

    # ソースに「zero」「completely」「proven」等が含まれているか（簡易チェック）
    source_has_it = any(
        en in source_text
        for en in ["zero", "completely", "proven", "eliminates", "no friction", "no app-switching"]
    )

    if not source_has_it:
        ctx = body[max(0, m.start() - 20): m.end() + 40].replace("\n", " ")
        warnings.append(
            f"絶対語の誇張の疑い: 「{ctx[:70]}」— "
            f"「{absolute_word}」はソースにある表現ですか？"
            "ソースが「大幅に減る」程度の表現なら、「大幅に削減できる」と書いてください"
        )
    return warnings


def check_strategy_inference_attribution(body: str, source_bodies: list[str]) -> list[str]:
    """
    企業の戦略・意図の推測が、帰属なしに事実として書かれていないかチェック。
    例: 「無料層を囲い込みPremium課金へ誘導する狙いがある」（Spotifyが明言していない）
    """
    warnings = []
    m = _STRATEGY_INFERENCE_RE.search(body)
    if not m:
        return warnings

    # 推測明示語（「と読める」「と考えられる」等）が近くにあるか
    vicinity = body[max(0, m.start() - 60): m.end() + 60]
    has_hedge = bool(re.search(
        r'(?:と読める|と考えられ|との見方|と推測される|とも(?:言える|見える)|'
        r'示唆され|可能性があ|かもしれ|とみられ)',
        vicinity,
    ))
    if not has_hedge:
        ctx = body[max(0, m.start() - 30): m.end() + 40].replace("\n", " ")
        warnings.append(
            f"戦略推測の帰属欠如: 「{ctx[:80]}」— "
            "企業が明言していない意図・戦略の推測には「と読める」「との見方もある」等を付けてください"
        )
    return warnings


def check_unsourced_elaboration(body: str, source_bodies: list[str]) -> list[str]:
    """
    ソースに書かれていない詳細説明・仕組み解説が追加されていないかチェック。
    特にQ&Aで「詳細は不明」としながら本文で説明してしまっている矛盾を検出。
    """
    warnings = []
    if not source_bodies:
        return warnings

    # Q&Aに「不明」「確認できない」「メタデータには含まれていない」が含まれているか
    qna_unknown_re = re.compile(
        r'(?:Q[.．&]|Q\.|## Q|### Q).{0,200}(?:不明|確認できない|記載がない|含まれていない)',
        re.DOTALL,
    )
    if not qna_unknown_re.search(body):
        return warnings

    # Q&A部分より前の本文でその同じトピックを詳しく説明していないか
    # （簡易チェック: Q&Aに「不明」があるのに本文が1800字以上の詳細を持つ場合）
    body_before_qa = re.split(r'## Q&A|### Q&A|# Q&A', body)[0]
    if len(body_before_qa) > 1800:
        warnings.append(
            "Q&Aで「詳細不明」としているトピックを、本文では詳しく説明している可能性があります。"
            "ソースに記載のない詳細はQ&Aでも本文でも書かず、「出典元を参照」と誘導してください"
        )
    return warnings


# タイトルの「N個/N点/Nつ/N選/Nポイント/N理由」を検出する regex
_TITLE_NUMBER_RE = re.compile(
    r'([1-9０-９一二三四五六七八九十]+)'
    r'(?:つ|個|点|件|選|ポイント|理由|項目|要素|特徴|メリット|デメリット)',
)
# 漢数字→算用数字変換
_KANJI_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _parse_title_number(s: str) -> int:
    """タイトル中の数字文字列を int に変換（漢数字・全角数字対応）。"""
    s = s.strip()
    if s in _KANJI_NUM:
        return _KANJI_NUM[s]
    # 全角数字を半角に
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    try:
        return int(s)
    except ValueError:
        return 0


def check_title_number_vs_body(title: str, body: str) -> list[str]:
    """
    タイトルで宣言した「N個/N点/Nつ」等の数と本文の列挙数が一致しているか検証。
    例: タイトル「4つのポイント」→ 本文で4点のリスト/H2が必要。
    """
    issues: list[str] = []
    m = _TITLE_NUMBER_RE.search(title)
    if not m:
        return issues

    declared_n = _parse_title_number(m.group(1))
    if declared_n < 2:
        return issues

    # 本文の列挙パターンを数える
    # ① H2見出し（## ...）
    h2_count  = len(re.findall(r'^## .+', body, re.MULTILINE))
    # ② 番号付き箇条書き（1. / ① 等）
    num_list  = len(re.findall(r'^\s*(?:[①②③④⑤⑥⑦⑧⑨⑩]|\d+[.．])\s+\S', body, re.MULTILINE))
    # ③ 太字番号（**1.** / **①** 等）
    bold_num  = len(re.findall(r'\*\*\s*(?:[①②③④⑤⑥⑦⑧⑨]|\d+[.．])', body))

    max_count = max(h2_count, num_list, bold_num)

    if max_count < declared_n:
        issues.append(
            f"タイトルで「{m.group(0)}」と宣言しているのに、"
            f"本文で列挙が{max_count}件しか見つかりません（H2={h2_count}/番号リスト={num_list}/太字番号={bold_num}）。"
            f"ソースにある{declared_n}件を本文に箇条書きまたはH2見出しで明示してください。"
        )
    return issues


# ソース内の具体的数値を検出する（日本語テキスト対応: \b の代わりに (?<!\d) を使用）
_CONCRETE_NUM_RE = re.compile(
    r'(?<!\d)\d[\d,.]*\s*(?:g|mAh|mm|GB|TB|MHz|GHz|fps|ms|%|ドル|\$|円|本|件|人|台|万|億)',
    re.IGNORECASE,
)


def check_source_richness(body: str, source_bodies: list[str]) -> list[str]:
    """
    ソースに含まれる具体的な数値・固有名詞が記事に取り込まれているか検証。
    ソースに数値が複数あるのに記事にほぼ含まれていない場合はWARN。
    """
    warnings: list[str] = []
    if not source_bodies:
        return warnings

    # ソース全体から具体的な数値を抽出（最大20件）
    source_nums: list[str] = []
    for sb in source_bodies:
        source_nums.extend(_CONCRETE_NUM_RE.findall(sb))
    if len(source_nums) < 3:
        return warnings  # ソースに数値が少なければスキップ

    # 記事に含まれる数値数
    body_nums = _CONCRETE_NUM_RE.findall(body)

    # ソース数値の20%以上が記事に含まれているかざっくり確認
    # （完全一致は要求しない——単位の表記揺れがあるため）
    source_num_set = {re.sub(r'\s', '', n) for n in source_nums[:20]}
    body_num_set   = {re.sub(r'\s', '', n) for n in body_nums}
    overlap = source_num_set & body_num_set

    if len(source_num_set) >= 3 and len(overlap) < 2:
        sample = list(source_num_set)[:5]
        warnings.append(
            f"ソースにある具体的な数値（例: {', '.join(sample[:3])}）が記事にほとんど含まれていません。"
            "重量・容量・スペック等の具体的な数値はソースから必ず引用して記事の信頼性と価値を高めてください。"
        )
    return warnings


# 地域限定キーワード（英語ソースでよく見られる表現）
_REGION_LIMIT_EN = re.compile(
    r'\b(?:US(?:-only| only| model|モデル)|United States only|'
    r'available in the US|US version|domestic|'
    r'Japan(?:-only| only)|EU only|carrier-locked)\b',
    re.IGNORECASE,
)
_REGION_LIMIT_JA = re.compile(
    r'(?:米国版|海外版|日本版|国内版|一部の地域|特定の地域|限定モデル|SIMフリー版)',
)


def check_region_specificity(body: str, source_bodies: list[str]) -> list[str]:
    """
    ソースに地域限定の記述がある場合に、記事でも明記されているかチェック。
    """
    warnings: list[str] = []
    source_text = " ".join(source_bodies)

    if not _REGION_LIMIT_EN.search(source_text):
        return warnings  # ソースに地域限定表現がなければスキップ

    if not (_REGION_LIMIT_JA.search(body) or _REGION_LIMIT_EN.search(body)):
        warnings.append(
            "ソースに地域限定（米国版のみ・特定地域のみ等）の記述がありますが、"
            "記事でその旨が明記されていません。"
            "「〜は米国版のみの仕様です」等、適用範囲を明示してください。"
        )
    return warnings


# ─────────────────────────────────────────────
# Pass 3: ウェブ検索ファクトチェック（Anthropic 内蔵 web_search_20250305）
# ─────────────────────────────────────────────

MAX_TOOL_LOOP = 10  # tool_use ループ上限（無限ループ防止）

_WEB_FACT_SYSTEM = """\
あなたはTech Gear Guideの上級ファクトチェッカーです。
web_search ツール（Anthropic 内蔵）を使って、記事の主要な主張を独立したウェブソースで検証してください。

【検証の進め方】
1. 記事から「検証が必要な主要な主張」を特定する（最大6件）
   優先順位:
   ① タイトルで数を宣言（「4つ」等）→ 本文でその数が列挙されているか
   ② アナリスト・リーク情報の断定化（「開発中」「参加」等）
   ③ 固有の数値・スペック・価格・日付（複数ソースで確認）
   ④ 企業の公式アクション（発表/確認/否定）
   ⑤ 競合製品の仕様（Apple Fitness+のiPhone単体対応等の最新情報）
   ⑥ 絶対語の根拠（ゼロ・完全に・証明等）
2. 各主張について英語の検索クエリを作り web_search を呼ぶ（最大6回）
3. 検索結果を記事と比較し、食い違い・誇張・断定化・未確認情報・最新情報との乖離を特定する
4. 最後に必ず JSON のみを出力する（コードブロック不要）

【出力形式（最終ターンで必ずこの形式のJSONのみを出力）】
{"web_verdict": "accurate"|"minor_issues"|"major_issues", "web_issues": ["問題の具体的説明（出典URLも可）"], "sources_checked": ["確認したURL"], "confidence": 0.0-1.0}
"""

_WEB_FACT_PROMPT = """\
以下の記事をウェブ検索で事実確認してください。

【確認重点項目（優先順）】
1. タイトルに「N個/N点/Nつ/Nポイント/N理由」がある場合：
   → 本文でその数が明示されているか確認し、またウェブで記事元のリストを検索して比較する
   例: 「4つのポイント」→ ウェブで「Android Authority Pixel 10a advantages」等を検索して4点を確認
2. アナリスト観測・リーク情報が「開発中」「参加」等の断定形で書かれていないか
3. 価格・スペック・発売日・重量・容量の数値は複数の独立ソースで確認できるか
4. 企業（OpenAI・Qualcomm・MediaTek・Apple・Google・Microsoft等）が公式にコメントまたは否定しているか
5. 比較記事での競合製品の仕様が最新・正確か
   例: 「Apple Fitness+はApple Watch必須」→ 現在の仕様を検索して確認
6. 「ゼロ」「完全に解決」「証明」等の絶対語の根拠はウェブ上に存在するか
7. 地域限定仕様（米国版のみ等）が記事で明記されているか

【検証対象記事】
タイトル: {title}

{article_body}
"""

async def ai_web_fact_judge_one(
    client: anthropic.AsyncAnthropic,
    article: dict,
    sem: asyncio.Semaphore,
) -> dict:
    """
    Anthropic 内蔵 web_search ツール（web_search_20250305）でウェブファクトチェックを行う。
    DDG 不要・ボット検知なし。Anthropic がサーバーサイドで検索を実行し結果をレスポンスに含める。
    """
    _empty = {"web_verdict": "skipped", "web_issues": [], "sources_checked": [], "confidence": 0.0}

    async with sem:
        title = article.get("title", "")
        body  = article.get("body", "")

        prompt = _WEB_FACT_PROMPT.format(
            title=title,
            article_body=body[:5500],
        )
        messages: list[dict] = [{"role": "user", "content": prompt}]
        sources_checked: list[str] = []

        for _turn in range(MAX_TOOL_LOOP):
            try:
                resp = await client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=_WEB_FACT_SYSTEM,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=messages,
                )
            except Exception as e:
                print(f"  ⚠️  [WEB事実確認] APIエラー ({title[:30]}): {e}")
                return _empty

            messages.append({"role": "assistant", "content": resp.content})

            # server_tool_use（検索クエリのログ）と web_search_tool_result（ソースURL収集）を処理
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "server_tool_use" and getattr(block, "name", "") == "web_search":
                    q = (block.input or {}).get("query", "")
                    print(f"    🔍 WEB [{title[:22]}] {q[:65]}")
                elif btype == "web_search_tool_result":
                    content = getattr(block, "content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                url = item.get("url", "")
                                if url:
                                    sources_checked.append(url)

            if resp.stop_reason in ("end_turn", "max_tokens"):
                # レスポンスのテキストブロックから JSON を抽出
                full_text = " ".join(
                    getattr(b, "text", "") for b in resp.content if hasattr(b, "text")
                )
                m = re.search(r'\{[^{}]*"web_verdict"[^{}]*\}', full_text, re.DOTALL)
                if m:
                    try:
                        result = json.loads(m.group())
                        result["sources_checked"] = list(
                            dict.fromkeys(sources_checked + result.get("sources_checked", []))
                        )
                        return result
                    except json.JSONDecodeError:
                        pass
                return _empty

        return _empty


async def run_ai_web_fact_judges(
    client: anthropic.AsyncAnthropic,
    articles: list[dict],
    sem: asyncio.Semaphore,
) -> list[dict]:
    """全記事に対してウェブ検索ファクトチェックを並列実行（Semaphoreで同時実行数制限）。"""
    tasks = [ai_web_fact_judge_one(client, a, sem) for a in articles]
    return list(await asyncio.gather(*tasks))


# ── 品質AI監査プロンプト ──────────────────────

_AI_QUALITY_SYSTEM = (
    "あなたはTech Gear Guideの読者体験・コンテンツ品質担当編集者です。"
    "記事の「面白さ」「完読率」「読者にとっての価値」を厳しく評価します。"
    "必ずJSON形式のみで回答してください。"
)

_AI_QUALITY_PROMPT = """\
以下の記事を「読者体験・品質・エンゲージメント」の観点で評価してください。
対象読者: テックリテラシーが高い日本人（20〜40代）。英語メディアを読む手間を省きつつ、
「翻訳メディアでは得られない深い示唆」を求めている層です。

【評価項目】10点満点で総合スコアをつけ、各項目の問題を列挙してください。

1.【リード文の引き付け力】
   - 冒頭2〜3文で「これは読む価値がある」と思わせているか
   - 具体的な数値・驚きの事実・意外な切り口があるか
   - 「○○が発表されました」等の平凡な書き出しになっていないか

2.【「So What?」の明示 — 読者にとっての意味】
   - 「それがどうした？」「自分に何が関係するの？」に答えているか
   - 技術的な事実を「ユーザーが体感できる変化」に翻訳しているか
   - 読者が「だから何？」と思う段落が残っていないか

3.【独自の示唆・洞察】
   - 単なるソース要約を超えた「なぜ今なのか」「業界文脈でどう読むか」があるか
   - 競合・市場・前世代との対比など、ソースにない深掘りがあるか（※ソースにない事実の捏造は別問題）
   - 読者が「ここでしか読めない視点だ」と感じる部分があるか

4.【情報密度・具体性】
   - 意味のない空白（「注目が集まっています」「期待が高まっています」等）が多くないか
   - 各段落に読者が持ち帰れる具体的な情報（数値・比較・判断基準）があるか
   - 「ふわっとした説明」で終わっている箇所はないか

5.【完読を促す構成・流れ】
   - 各セクションが「次も読みたい」という動機を作っているか
   - 見出しに続きを読む理由（好奇心・実益）があるか
   - FAQが形式的でなく、読者の本当の疑問に答えているか

6.【文章品質・読みやすさ】
   - 「なお、」「また、」「さらに、」の多用でリズムが単調になっていないか
   - 一文が長すぎて読みにくい箇所がないか
   - 同じ表現・フレーズが繰り返されていないか

7.【記事の差別化・ユニークバリュー】
   - 「Google翻訳でも読める記事」と何が違うか明確か
   - 読者が「この記事を読んでよかった」「シェアしたい」と思える要素があるか
   - Tech Gear Guideならではの専門性・視点が出ているか

JSON形式のみで回答（コードブロック不要）:
{{"quality_score": 0-10, "quality_verdict": "high"|"medium"|"low", "quality_issues": ["具体的な問題と改善案（例: リード文が「〜が発表されました」で始まり引き付けが弱い。冒頭に「最大60%」という数値を入れると効果的）"], "strengths": ["記事の良い点（例: スタートメニューの体感比較が具体的で読者に刺さる）"]}}

【評価対象記事】
{article_body}
"""

async def _no_quality_ai() -> dict:
    return {"quality_score": 0, "quality_verdict": "skipped", "quality_issues": [], "strengths": []}

async def _no_source_ai() -> dict:
    return {"verdict": "no_source", "issues": [], "confidence": 0.0}

async def ai_fact_judge_one(
    client: anthropic.AsyncAnthropic,
    article_body: str,
    source_body: str,
    published_at: str,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        prompt = _AI_PROMPT.format(
            source_body=source_body[:4500],
            article_body=article_body,
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
            print(f"  ⚠️  [事実確認] AIエラー: {e}")
        return {"verdict": "unknown", "issues": [], "confidence": 0.0}

async def ai_quality_judge_one(
    client: anthropic.AsyncAnthropic,
    article_body: str,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        prompt = _AI_QUALITY_PROMPT.format(article_body=article_body[:5000])
        try:
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=1200,
                system=_AI_QUALITY_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"  ⚠️  [品質監査] AIエラー: {e}")
        return {"quality_score": 0, "quality_verdict": "unknown", "quality_issues": [], "strengths": []}

async def run_ai_fact_judges(
    client: anthropic.AsyncAnthropic,
    articles: list[dict],
    source_map: dict,
    sem: asyncio.Semaphore,
) -> list[dict]:
    tasks = []
    for a in articles:
        bodies       = _source_bodies(a, source_map)
        published_at = a.get("published_at", datetime.now(timezone.utc).isoformat())
        if bodies:
            combined_source = "\n\n---\n\n".join(bodies[:3])[:5000]
            tasks.append(ai_fact_judge_one(client, a.get("body", ""), combined_source, published_at, sem))
        else:
            tasks.append(_no_source_ai())
    return list(await asyncio.gather(*tasks))

async def run_ai_quality_judges(
    client: anthropic.AsyncAnthropic,
    articles: list[dict],
    sem: asyncio.Semaphore,
) -> list[dict]:
    tasks = [
        ai_quality_judge_one(client, a.get("body", ""), sem)
        for a in articles
    ]
    return list(await asyncio.gather(*tasks))

async def run_all_ai_judges(
    client: anthropic.AsyncAnthropic,
    articles: list[dict],
    source_map: dict,
    skip_quality: bool = False,
    skip_web: bool = False,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Pass1（事実確認）・Pass2（品質）を並列実行し、
    Pass3（ウェブ検索ファクトチェック）を直列で追加実行する。
    戻り値: (fact_results, quality_results, web_results)
    """
    sem = asyncio.Semaphore(MAX_PARALLEL)

    # Pass1 + Pass2
    if skip_quality:
        fact_results    = await run_ai_fact_judges(client, articles, source_map, sem)
        quality_results = [{"quality_score": 0, "quality_verdict": "skipped", "quality_issues": [], "strengths": []} for _ in articles]
    else:
        fact_task    = run_ai_fact_judges(client, articles, source_map, sem)
        quality_task = run_ai_quality_judges(client, articles, sem)
        fact_results, quality_results = await asyncio.gather(fact_task, quality_task)

    # Pass3: ウェブ検索ファクトチェック（Jina Search・APIキー不要）
    if skip_web:
        web_results = [{"web_verdict": "skipped", "web_issues": [], "sources_checked": [], "confidence": 0.0} for _ in articles]
    else:
        print("  🌐 Pass3: ウェブ検索ファクトチェック実行中...")
        # Anthropic web_search 並列数（レートリミット次第で調整）
        web_sem     = asyncio.Semaphore(5)
        web_results = await run_ai_web_fact_judges(client, articles, web_sem)

    return fact_results, quality_results, web_results

# ─────────────────────────────────────────────
# 単体記事監査
# ─────────────────────────────────────────────

def audit_article(
    article: dict,
    source_map: dict,
    ai_fact_result: Optional[dict] = None,
    ai_quality_result: Optional[dict] = None,
    ai_web_result: Optional[dict] = None,
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

    # ── タイトルの確定表現・煽り語句 ──
    for w in check_title_accuracy(title, article):
        warnings.append(w)

    # ── H2見出し数 ──
    for w in check_h2_count(body):
        warnings.append(w)

    # ── 出典URL存在確認 ──
    for i in check_source_urls(article):
        issues.append(i)

    # ── 常套句締め文句（AI感）──
    for w in check_cliched_endings(body):
        warnings.append(w)

    # ── 記事タイプ別バリデーション ──
    for w in check_article_type_rules(article):
        warnings.append(w)

    # ── 極端な%表示 ──
    for w in check_extreme_percentage(body):
        warnings.append(w)

    # ── 単一原因への過帰属 ──
    for w in check_single_cause_overattribution(body):
        warnings.append(w)

    # ── ダミー機・APK解析の情報源明記 ──
    for w in check_leak_source_clarity(article):
        warnings.append(w)

    # ── 空虚フレーズ（品質） ──
    for w in check_empty_phrases(body):
        warnings.append(w)

    # ── リード文品質 ──
    for w in check_lead_quality(body):
        warnings.append(w)

    # ── 接続詞多用（AI感） ──
    for w in check_connector_overuse(body):
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

        # ── 企業向け機能の一般化 ──
        for w in check_enterprise_feature_generalization(body, src_bodies):
            warnings.append(w)

        # ── 情報源階層の混同（メディア解釈を企業発言として断定） ──
        for w in check_source_attribution_hierarchy(body, src_bodies):
            warnings.append(w)

        # ── メディア評価語の事実断定化 ──
        for w in check_media_evaluation_words(body, src_bodies):
            warnings.append(w)

        # ── 数量単位の誤変換（records→顧客/ユーザー） ──
        for w in check_unit_conflation(body, src_bodies):
            warnings.append(w)

        # ── 比較優位の無条件化（上位機に勝つ等） ──
        for w in check_conditional_superiority(body, src_bodies):
            warnings.append(w)

        # ── 絶対語の誇張（ゼロ・完全に・実機で証明等） ──
        for w in check_absolute_words(body, src_bodies):
            warnings.append(w)

        # ── ビジネス戦略推測の帰属欠如 ──
        for w in check_strategy_inference_attribution(body, src_bodies):
            warnings.append(w)

        # ── ソース外詳細補完とQ&A矛盾 ──
        for w in check_unsourced_elaboration(body, src_bodies):
            warnings.append(w)

        # ── ソース具体情報の引き継ぎ（数値・固有名詞） ──
        for w in check_source_richness(body, src_bodies):
            warnings.append(w)

        # ── 地域限定情報の明記 ──
        for w in check_region_specificity(body, src_bodies):
            warnings.append(w)

    else:
        warnings.append("ソース本文が取得できていません（grounding不可）")

    # ── タイトル数字と本文列挙の整合性 ──
    for i in check_title_number_vs_body(title, body):
        issues.append(i)

    # ── アナリスト帰属チェック（ソースに依存しない） ──
    for w in check_analyst_claim_attribution(body, article):
        warnings.append(w)

    # ── Pass1: 事実確認AI結果 ──
    ai_verdict = None
    if ai_fact_result:
        verdict    = ai_fact_result.get("verdict", "unknown")
        ai_verdict = verdict
        for issue in ai_fact_result.get("issues", []):
            if verdict == "major_issues":
                issues.append(f"[事実AI] {issue}")
            elif verdict == "minor_issues":
                warnings.append(f"[事実AI] {issue}")

    # ── Pass2: 品質AI結果 ──
    quality_score   = 0
    quality_verdict = "skipped"
    quality_issues: list[str] = []
    strengths:      list[str] = []

    if ai_quality_result and ai_quality_result.get("quality_verdict") not in ("skipped", "unknown", None):
        quality_score   = ai_quality_result.get("quality_score", 0)
        quality_verdict = ai_quality_result.get("quality_verdict", "unknown")
        quality_issues  = ai_quality_result.get("quality_issues", [])
        strengths       = ai_quality_result.get("strengths", [])
        for qi in quality_issues:
            warnings.append(f"[品質AI] {qi}")

    # ── Pass3: ウェブ検索ファクトチェック結果 ──
    web_verdict  = "skipped"
    web_issues:  list[str] = []
    web_sources: list[str] = []

    if ai_web_result and ai_web_result.get("web_verdict") not in ("skipped", "unknown", None):
        web_verdict  = ai_web_result.get("web_verdict", "unknown")
        web_issues   = ai_web_result.get("web_issues", [])
        web_sources  = ai_web_result.get("sources_checked", [])
        # ウェブ検索が全件失敗（0件）の場合は検証不能扱い → major_issuesをWARNに格下げ
        # confidence値に関わらず、取得ソース数0件なら検索失敗とみなす（DDGボット検知対策）
        search_failed = len(web_sources) == 0
        for wi in web_issues:
            if web_verdict == "major_issues" and not search_failed:
                issues.append(f"[WEB] {wi}")
            else:
                # 検索失敗 or minor_issues はWARN
                warnings.append(f"[WEB] {wi}")

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")

    return {
        "slug":            slug,
        "title":           title[:60],
        "category":        cat,
        "body_len":        len(body),
        "status":          status,
        "issues":          issues,
        "warnings":        warnings,
        "ai_verdict":      ai_verdict,
        "web_verdict":     web_verdict,
        "web_issues":      web_issues,
        "web_sources":     web_sources,
        "quality_score":   quality_score,
        "quality_verdict": quality_verdict,
        "quality_issues":  quality_issues,
        "strengths":       strengths,
        "has_source":      bool(src_bodies),
        "audited_at":      datetime.now(timezone.utc).isoformat(),
    }

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ai-check",      action="store_true", help="AI監査を全スキップ（コスト節約）")
    parser.add_argument("--no-quality-check", action="store_true", help="品質AI監査のみスキップ（事実確認は実施）")
    parser.add_argument("--no-web-check",     action="store_true", help="ウェブ検索ファクトチェックをスキップ")
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

    fact_results:    list[Optional[dict]]
    quality_results: list[Optional[dict]]
    web_results:     list[Optional[dict]]

    if args.no_ai_check:
        print("AI監査: 全スキップ（--no-ai-check）")
        fact_results    = [None] * len(articles)
        quality_results = [None] * len(articles)
        web_results     = [None] * len(articles)
    elif articles:
        skip_quality = args.no_quality_check
        skip_web     = args.no_web_check
        mode_parts   = ["事実確認"]
        if not skip_quality:
            mode_parts.append("品質")
        if not skip_web:
            mode_parts.append("ウェブ検索")
        print(f"AI監査を実行中... [{'・'.join(mode_parts)}]")
        client = anthropic.AsyncAnthropic()
        fact_results, quality_results, web_results = await run_all_ai_judges(
            client, articles, source_map,
            skip_quality=skip_quality,
            skip_web=skip_web,
        )
    else:
        fact_results    = []
        quality_results = []
        web_results     = []

    reports = [
        audit_article(a, source_map, f_r, q_r, w_r)
        for a, f_r, q_r, w_r in zip(articles, fact_results, quality_results, web_results)
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        for r in reports:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pass_ = sum(1 for r in reports if r["status"] == "PASS")
    warn_ = sum(1 for r in reports if r["status"] == "WARN")
    fail_ = sum(1 for r in reports if r["status"] == "FAIL")

    quality_scores = [r["quality_score"] for r in reports if r.get("quality_score", 0) > 0]
    avg_quality    = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    # ウェブチェック結果の集計
    web_major  = sum(1 for r in reports if r.get("web_verdict") == "major_issues")
    web_minor  = sum(1 for r in reports if r.get("web_verdict") == "minor_issues")
    web_ok     = sum(1 for r in reports if r.get("web_verdict") == "accurate")
    web_skip   = sum(1 for r in reports if r.get("web_verdict") in ("skipped", "unknown", None))
    total_srcs = sum(len(r.get("web_sources", [])) for r in reports)

    print(f"\n{'='*50}")
    print(f"  正確性: PASS {pass_} / WARN {warn_} / FAIL {fail_}")
    if quality_scores:
        print(f"  品質スコア: 平均 {avg_quality:.1f}/10  "
              f"(高:{sum(1 for r in reports if r.get('quality_verdict')=='high')} / "
              f"中:{sum(1 for r in reports if r.get('quality_verdict')=='medium')} / "
              f"低:{sum(1 for r in reports if r.get('quality_verdict')=='low')})")
    if not web_skip == len(reports):
        print(f"  🌐 ウェブ検索: 正確 {web_ok} / 軽微 {web_minor} / 重大 {web_major}  "
              f"（{total_srcs}件のURLを確認）")
    print(f"{'='*50}")

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
                if r.get("web_sources"):
                    print(f"    🌐 確認URL: {', '.join(r['web_sources'][:3])}")

    # 品質スコアが低い記事を表示
    low_quality = [r for r in reports if r.get("quality_verdict") == "low"]
    if low_quality:
        print("\n── 品質LOW 詳細 ──")
        for r in low_quality:
            print(f"  [{r['slug']}] スコア:{r['quality_score']}/10")
            for qi in r.get("quality_issues", [])[:3]:
                print(f"    ◆ {qi}")
            for s in r.get("strengths", [])[:1]:
                print(f"    ✓ {s}")

    print(f"\n→ correct.py に渡します（FAIL {fail_}件・WARN {warn_}件を修正対象とします）")

    if len(articles) > 0 and fail_ / len(articles) > 0.7:
        print("FAILが70%超。correct.py で修正を続行します。")


if __name__ == "__main__":
    asyncio.run(main())
