# -*- coding: utf-8 -*-
"""
DeviceBrief generate.py 設計ドラフト v4

変更点 (v4): Progressive Article対応
  - progressive_slugs_cache.json でトピック別の既存スラッグを追跡
  - B型続報が同トピックの既存記事を検出したとき → Phase 2/3 更新記事として生成
  - MUST_CATCH の A型速報は生成後にキャッシュへ登録 → 次バッチでPhase 2候補になる
  - C型/MUST_CATCH は常に新URL（Progressive対象外）
"""

import asyncio
import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic

MODEL                   = "claude-sonnet-4-6"
MAX_PARALLEL            = 5
INPUT_PATH              = Path("collected_articles.jsonl")
OUTPUT_PATH             = Path("generated_articles.jsonl")
PROGRESSIVE_CACHE_PATH  = Path("progressive_slugs_cache.json")

# キャッシュの有効期限（時間）。この時間を超えたエントリは Phase 3 完了とみなしクリア
PROGRESSIVE_CACHE_TTL_H = 72

# ─────────────────────────────────────────────
# データ型
# ─────────────────────────────────────────────

@dataclass
class RawArticle:
    url: str
    title: str
    body: str
    source_name: str
    tier: int
    category: str
    published: str
    fetch_method_used: str
    body_len: int = 0
    is_leak: bool = False
    is_must_catch: bool = False
    score: float = 0.0
    url_hash: str = ""

@dataclass
class GeneratedArticle:
    title: str
    slug: str
    category: str
    tags: list[str]
    article_type: str
    body: str
    seo_description: str
    sources: list[dict]
    source_reliability: int
    published_at: str
    is_must_catch: bool
    is_leak: bool
    original_score: float
    source_names: str
    progressive_phase: Optional[int] = None     # None=通常新記事 / 2=Phase2更新 / 3=Phase3更新
    progressive_target_slug: Optional[str] = None  # Phase2/3時: PATCH対象のslug

# ─────────────────────────────────────────────
# Progressive Articleキャッシュ管理
# ─────────────────────────────────────────────

def load_progressive_cache() -> dict:
    """
    progressive_slugs_cache.json を読み込む。
    構造: { "topic_key": {"slug": "...", "phase": 1, "published_at": "...", "body_len": N} }
    """
    if not PROGRESSIVE_CACHE_PATH.exists():
        return {}
    with open(PROGRESSIVE_CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_progressive_cache(cache: dict):
    with open(PROGRESSIVE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def _purge_expired_cache(cache: dict) -> dict:
    """TTLを超えたエントリを削除（Phase 3完了・古い速報のクリーンアップ）"""
    now = datetime.now(timezone.utc)
    active = {}
    for key, entry in cache.items():
        try:
            published = datetime.fromisoformat(entry["published_at"])
            age_h = (now - published).total_seconds() / 3600
            if age_h <= PROGRESSIVE_CACHE_TTL_H:
                active[key] = entry
        except Exception:
            pass
    return active

def determine_progressive_phase(topic_key: str, cache: dict) -> tuple[Optional[int], Optional[str]]:
    """
    B型続報の生成時に呼ぶ。
    同トピックが既にキャッシュにあれば (next_phase, existing_slug) を返す。
    なければ (None, None) → 新規URL記事として生成。
    """
    entry = cache.get(topic_key)
    if not entry:
        return None, None
    current_phase = entry.get("phase", 1)
    if current_phase >= 3:
        return None, None   # Phase 3完了済みなら新規記事として扱う
    return current_phase + 1, entry["slug"]

def register_to_cache(cache: dict, topic_key: str, slug: str, phase: int, body_len: int):
    """生成成功後にキャッシュへ登録・更新"""
    cache[topic_key] = {
        "slug":         slug,
        "phase":        phase,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "body_len":     body_len,
    }

# ─────────────────────────────────────────────
# B型グループ化 / C型判定
# ─────────────────────────────────────────────

B_TYPE_KEYWORDS = [
    "iphone 17","iphone 18","galaxy s26","galaxy z fold 7",
    "rtx 5090","rtx 5080","rx 9070","apple m5",
    "windows 12","surface pro 12",
    "gpt-5","gemini 2.5","claude 4","pixel 10",
]

def _topic_key(title: str) -> Optional[str]:
    t = title.lower()
    for kw in B_TYPE_KEYWORDS:
        if kw in t:
            return kw
    return None

def group_for_b_type(articles: list[RawArticle]) -> dict[str, list[RawArticle]]:
    groups: dict[str, list[RawArticle]] = {}
    for a in articles:
        key = _topic_key(a.title)
        if key:
            groups.setdefault(key, []).append(a)
    # 3ソース以上あるか、キャッシュに既存エントリがある（続報）トピックを対象にする
    return {k: v for k, v in groups.items() if len(v) >= 2}

def is_c_type(a: RawArticle) -> bool:
    return a.is_must_catch and a.is_leak

SOURCE_RELIABILITY: dict[str, int] = {
    "bloomberg": 5, "9to5mac": 4, "9to5google": 4,
    "windows central": 4, "macrumors": 3, "wccftech": 3,
    "videocardz": 3, "notebookcheck": 3, "neowin": 2, "techradar": 2,
}

def get_reliability(source_name: str) -> int:
    for key, val in SOURCE_RELIABILITY.items():
        if key in source_name.lower():
            return val
    return 2

# ─────────────────────────────────────────────
# システムプロンプト
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """\
あなたはDeviceBriefの上級編集者です。
海外テックメディアの記事を日本人読者向けに翻訳・解説する専門家です。

【絶対ルール】
1. ソーステキストにある情報のみを使う（ハルシネーション禁止）
2. 数字・スペック・日付・価格はソース通りに記載（改変禁止）
3. ソースにない情報を推測で補わない
4. 語調は必ずです・ます調（だ・である調は文末で使用禁止）
5. 出典URLは必ず記載する

【文体ルール】
- 文末は「〜です」「〜ます」「〜しています」「〜されています」
- 「〜だ」「〜である」単体での文末は禁止
- 読者に語りかける自然な文体を心がける
- 「なお、」「また、」「さらに、」の多用はAIっぽくなるので控える

【ユーザー価値の原則】
- 事実を伝えるだけでなく「それが読者にとって何を意味するか」を、記事の内容上自然に加えられる場合は加える（無理に全記事へ入れない）
- 数値が出てきたら、体感できる言葉に翻訳できる場合は翻訳する
  例: 「3nmプロセス採用」→「前世代より消費電力が約30%下がり、同じバッテリーでより長く使えます」
  例: 「RAM 4GB増加」→「4K動画の同時編集が現実的になります」
- 読者が「なぜ今なのか」「競合と何が違うのか」と疑問に思いそうな場合は、自然な流れで先回りして答える

【記事の面白さを上げる具体的なコツ】
- 業界の「裏にある動き」を読む（競合関係・市場シェア・タイミングの意味）
- 「前回の予測と今回の情報の違い」があれば指摘する
- 技術的な内容は「それがユーザー体験にどう変わるか」に落とす
"""

# ─────────────────────────────────────────────
# カテゴリ別深掘り指示
# ─────────────────────────────────────────────

CATEGORY_DEEP_DIVE: dict[str, str] = {
    "smartphone": """\
【スマートフォン記事の深掘り指示】
- バッテリー・カメラ・パフォーマンスの変化は「前世代比で何が体感できるか」に落とす
- 価格変化があれば「日本円換算」を添える（ソースに価格があれば）
- 日本発売・キャリア対応はソースに情報がある場合のみ言及する
- 「買い換えを検討すべきか」という読者視点の判断軸を入れる
""",
    "tablet": """\
【タブレット記事の深掘り指示】
- 「どんな用途に向いているか」（iPad Pro→クリエイター、Surface→ビジネス等）を明示する
- Apple PencilやSmart Keyboard等の周辺機器との関係性に触れる
- iPadとMacの機能差・棲み分けが変化する場合は指摘する
""",
    "windows": """\
【Windows記事の深掘り指示】
- 更新によって「何が変わるか」「何ができなくなるか」を明確にする
- 企業ユーザーと個人ユーザーへの影響を分けて考える
- 既知の不具合・副作用がある場合は冒頭近くで警告する
- 「今すぐ更新すべきか、しばらく待つべきか」の判断材料を示す
""",
    "cpu_gpu": """\
【CPU・GPU記事の深掘り指示】
- ベンチマーク数値は「実際のゲームや作業でどう変わるか」に翻訳する
  例: 「GeekbenchシングルスコアX」→「○○より△%速い処理速度」
- 価格帯・コストパフォーマンスの観点を入れる（ソースに情報があれば）
- IntelvsAMD、NVIDIAvsAMDの競争文脈を踏まえた解説を入れる
- 「誰が買うべき製品か」（ゲーマー／クリエイター／一般ユーザー）を示す
""",
    "ai": """\
【AI記事の深掘り指示】
- 機能を「具体的な使用シーン」で説明する（抽象的な能力説明ではなく）
  例: 「マルチモーダル対応」→「会議の録音をそのまま要約依頼できます」
- 競合AI（ChatGPT/Gemini/Claude/Copilot）との実質的な違いを示す
- 「無料プランで使えるか」「日本語は自然か」は読者の最重要関心事なので必ず触れる
- プライバシー・データ利用ポリシーの変化があれば指摘する
""",
    "xr": """\
【XR・AR・VR記事の深掘り指示】
- Apple Vision Pro / Meta Quest / PlayStation VRなど機種を明確に区別する
- 「スマホやPCとの違い・使い分け」を読者視点で説明する
- 没入感・操作感・コンテンツ対応状況など体験に直結する情報を重視する
- 価格・日本発売有無・日本語コンテンツの充実度に必ず言及する
- 「今買うべきか・待つべきか」のアドバイスはXR市場の成熟度を踏まえて判断する
""",
    "wearable": """\
【ウェアラブル記事の深掘り指示】
- Apple Watch / Galaxy Watch / Pixel Watch など機種を明確に区別する
- バッテリー持続時間・健康トラッキング精度・スマホ連携の違いを具体的に示す
- AirPods / Galaxy Buds などイヤフォン系は音質・ノイキャン・装着感を重視する
- 「前世代から買い換えるべきか」のアドバイスを入れる
- スポーツ・健康管理・音楽・仕事用途など読者の使い方別に判断軸を示す
""",
    "general": """\
【一般記事の深掘り指示】
- 「なぜこのタイミングで発表されたのか」という業界文脈を入れる
- 読者の生活・仕事への具体的な影響を示す
""",
}

# ─────────────────────────────────────────────
# 読者アクション提案テンプレート
# ─────────────────────────────────────────────

ACTION_GUIDE = """\
【記事末尾の読者アクション提案】
記事の内容に応じて、以下のいずれかを自然な形で末尾近くに入れる（必ず入れるのではなく、
記事の性質上「判断材料を提供できる」場合のみ）:

- 製品が発売済み → 「購入を検討するなら〜がポイントです」
- 製品が発表済み・未発売 → 「発売まで待つ価値があるかどうかは〜次第です」
- アップデート系 → 「〜の環境では即座に適用すべき/慎重に様子を見た方がよい更新です」
- リーク系 → 「現時点では〜と判断するのが妥当です。続報を待ちましょう」

ただしムリに入れると不自然になるため、馴染まない記事では省略してよい。
"""

# ─────────────────────────────────────────────
# FAQセクション指示
# ─────────────────────────────────────────────

FAQ_GUIDE = """\
【FAQセクションについて】
記事末尾の出典の前に、2〜3問のQ&Aを入れる。
AIO（ChatGPT/Perplexity等への引用対策）と読者の疑問解消が目的。

フォーマット:
## Q&A

**Q. [読者が最も聞きたいこと]**
[簡潔な回答。1〜3文]

**Q. [2番目に多そうな疑問]**
[回答]

質問は「読者が実際にGoogleやChatGPTで検索しそうなもの」を想定してください。
情報が十分でFAQを入れるべき記事（スペック詳細・価格比較・使い方系）にのみ追加し、
短いニュース記事では省略してよい。
"""

# ─────────────────────────────────────────────
# プロンプトビルダー
# ─────────────────────────────────────────────

def build_a_type_prompt(a: RawArticle) -> str:
    deep_dive = CATEGORY_DEEP_DIVE.get(a.category, CATEGORY_DEEP_DIVE["general"])

    return f"""\
以下のソース記事を日本語のA型速報記事にしてください。

【記事仕様】
- 記事タイプ: A型速報
- 対象読者: テックリテラシー高めの日本人（20〜40代）
- 目標文字数: 1,500〜2,000字（ソース記事が短い場合は品質優先で柔軟化）
- 見出し数: H2を3〜5個

【見出し設計の原則】
- 見出しの内容は元記事のトピックを読み込んで自由に設定する
- 「事実→背景→日本市場→今後の展開」の固定パターンは禁止
- 記事ごとに自然な構成を作る

【見出し直下のサマリー】
- 情報が多い見出しの直後に、箇条書きかテーブルで要点をまとめる形式を時折使う
- 毎回使うのではなく、読者にとって一目でわかると便利な箇所のみ

{deep_dive}

{ACTION_GUIDE}

{FAQ_GUIDE}

【出力フォーマット（必ずこの形式で出力）】
---META---
title: [SEOタイトル・日本語・70字以内。具体的な数値・製品名を入れると強い]
slug: [英数字ハイフン区切り]
category: {a.category}
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: A型速報
seo_description: [150字以内。検索意図に直接回答する内容]
---END_META---

[リード文：2〜3行。です・ます調。読者が「続きを読みたい」と思う書き出し]

## [見出し1]

[本文]

## [見出し2]

[本文]

## [見出し3]

[本文]

<!-- 必要に応じてFAQと読者アクション提案を追加 -->

---

**出典**
- [{a.title}]({a.url}) — {a.source_name}

【ソース記事本文】
{a.body[:4000]}
"""


def build_b_type_prompt(articles: list[RawArticle], topic: str) -> str:
    sources_block = "\n\n".join(
        f"【ソース{i+1}: {a.source_name}】\n{a.body[:2000]}"
        for i, a in enumerate(articles[:5])
    )
    sources_citations = "\n".join(
        f"- [{a.title}]({a.url}) — {a.source_name}"
        for a in articles[:5]
    )
    primary = articles[0]
    deep_dive = CATEGORY_DEEP_DIVE.get(primary.category, CATEGORY_DEEP_DIVE["general"])

    return f"""\
以下の複数ソースを統合してB型深掘り記事を作成してください。

【記事仕様】
- 記事タイプ: B型深掘り
- トピック: {topic}
- 目標文字数: 1,800〜2,500字
- 見出し数: H2を4〜5個
- 語調: です・ます調

【B型記事の原則】
- 複数ソースを「並べる」のではなく「統合して一つの深い解説」にする
- 各ソースの見解が異なる部分は「○○によると〜だが、△△は〜と報じている」と明記する
- 単独ソースでは見えない「全体像」を読者に見せることがB型の価値

{deep_dive}

{ACTION_GUIDE}

{FAQ_GUIDE}

【出力フォーマット】
---META---
title: [SEOタイトル・日本語・70字以内]
slug: [英数字ハイフン区切り]
category: {primary.category}
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: B型深掘り
seo_description: [150字以内]
---END_META---

[リード文：2〜3行。です・ます調]

## [見出し1]
...

---

**出典**
{sources_citations}

{sources_block}
"""


def build_progressive_update_prompt(
    articles: list[RawArticle],
    topic: str,
    target_phase: int,
    existing_body: str,
) -> str:
    """
    Phase 2（詳細）または Phase 3（決定版）の更新記事を生成するプロンプト。
    既存記事のbodyを渡し、「新情報を統合して進化させる」指示を行う。
    """
    phase_labels = {2: "詳細版（Phase 2）", 3: "決定版（Phase 3）"}
    phase_label  = phase_labels.get(target_phase, f"Phase {target_phase}")
    target_chars = {2: "1,800〜2,500字", 3: "2,200〜3,000字"}.get(target_phase, "2,000字以上")

    sources_block = "\n\n".join(
        f"【新ソース{i+1}: {a.source_name}】\n{a.body[:2000]}"
        for i, a in enumerate(articles[:5])
    )
    sources_citations = "\n".join(
        f"- [{a.title}]({a.url}) — {a.source_name}"
        for a in articles[:5]
    )
    primary   = articles[0]
    deep_dive = CATEGORY_DEEP_DIVE.get(primary.category, CATEGORY_DEEP_DIVE["general"])

    return f"""\
以下の「既存記事」を、新しいソース情報を統合して「{phase_label}」に進化させてください。

【Progressive Article: {phase_label}の仕様】
- 目標文字数: {target_chars}
- 見出し数: H2を4〜5個
- 語調: です・ます調
- 既存記事のURLはそのまま（同じslugを使用）

【更新の原則】
- 既存記事の正確な情報はそのまま活かす（書き直しではなく「進化」）
- 新ソースで追加・修正された情報を統合する
- 矛盾する情報がある場合は「当初○○と報じられていたが、△△によると〜に修正された」と明記する
- Phase {target_phase}としての深さ: {"複数ソースの統合・技術詳細・比較表の追加" if target_phase == 2 else "全情報統合・FAQ充実・今後の予測・決定版としての包括性"}
- 記事冒頭に「最終更新: {datetime.now().strftime('%Y年%m月%d日')}」を含める

{deep_dive}

{FAQ_GUIDE}

【出力フォーマット（slugは既存のものを必ず引き継ぐ）】
---META---
title: [SEOタイトル（既存より情報量が増えた場合は更新可）]
slug: [既存記事と同じslug]
category: {primary.category}
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: B型深掘り
seo_description: [150字以内・更新後の内容を反映]
---END_META---

> **最終更新: {datetime.now().strftime('%Y年%m月%d日')}**

[リード文]

## [見出し1]
...

---

**出典**
{sources_citations}

【既存記事の本文】
{existing_body[:3000]}

【新しいソース情報】
{sources_block}
"""


def build_c_type_prompt(a: RawArticle) -> str:
    reliability = get_reliability(a.source_name)
    stars = "★" * reliability + "☆" * (5 - reliability)

    return f"""\
以下のリーク・噂記事をC型リーク記事にしてください。

【記事仕様】
- 記事タイプ: C型リーク
- ソース信頼度: {stars}（{reliability}/5）— {a.source_name}
- 目標文字数: 1,500〜2,000字
- 見出し数: H2を3〜5個
- 語調: です・ます調

【C型記事の原則】
- 確定情報とリーク情報を文中で必ず区別する
  確定: 「〜が確認されています」「〜と発表されました」
  リーク: 「〜と報告されています」「〜とされています」「〜の可能性があります」
- ソースの信頼性の根拠（過去の的中率・情報入手経路）を必ず解説する
- 「このリーク情報が正確だった場合、何が起きるか」の分析を加える
- 見出し直下に「確認済み情報テーブル」を入れると読者の理解が深まる

{ACTION_GUIDE}

{FAQ_GUIDE}

【出力フォーマット】
---META---
title: [SEOタイトル・「〜リーク」「〜流出」等・70字以内]
slug: [英数字ハイフン区切り]
category: {a.category}
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: C型リーク
source_reliability: {reliability}
seo_description: [150字以内]
---END_META---

> **情報の確度: {stars}**（出所: {a.source_name}）

[リード文：2〜3行。です・ます調]

## [見出し1]
...

---

**出典**
- [{a.title}]({a.url}) — {a.source_name}

【ソース記事本文】
{a.body[:4000]}
"""

# ─────────────────────────────────────────────
# メタデータパース・生成
# ─────────────────────────────────────────────

def parse_meta(text: str) -> dict:
    meta = {}
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

# ─────────────────────────────────────────────
# Claude API 呼び出し
# ─────────────────────────────────────────────

async def generate_article(
    client: anthropic.AsyncAnthropic,
    prompt: str,
    article_type: str,
    raw: RawArticle,
    sem: asyncio.Semaphore,
    progressive_phase: Optional[int] = None,
    progressive_target_slug: Optional[str] = None,
) -> Optional[GeneratedArticle]:
    async with sem:
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            meta = parse_meta(text)
            body = extract_body(text)

            if not meta.get("title") or len(body) < 500:
                print(f"  ⚠️  生成失敗: {raw.title[:50]}")
                return None

            # Progressive更新の場合はキャッシュのslugを使う
            slug = progressive_target_slug if progressive_target_slug else meta.get("slug", raw.url_hash)

            return GeneratedArticle(
                title=meta.get("title", raw.title),
                slug=slug,
                category=meta.get("category", raw.category),
                tags=parse_tags(meta.get("tags", "")),
                article_type=article_type,
                body=body,
                seo_description=meta.get("seo_description", ""),
                sources=[{"title": raw.title, "url": raw.url, "media": raw.source_name}],
                source_reliability=int(meta.get("source_reliability", 0)),
                published_at=datetime.now(timezone.utc).isoformat(),
                is_must_catch=raw.is_must_catch,
                is_leak=raw.is_leak,
                original_score=raw.score,
                source_names=raw.source_name,
                progressive_phase=progressive_phase,
                progressive_target_slug=progressive_target_slug,
            )
        except Exception as e:
            print(f"  ❌ API エラー: {e}")
            return None

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

async def main():
    if not INPUT_PATH.exists():
        print(f"入力ファイルが見つかりません: {INPUT_PATH}")
        return

    raw_articles: list[RawArticle] = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            raw_articles.append(RawArticle(**{k: d[k] for k in RawArticle.__dataclass_fields__}))

    print(f"入力: {len(raw_articles)} 件")

    # ── Progressive キャッシュ読み込み・有効期限切れ削除 ──
    prog_cache = _purge_expired_cache(load_progressive_cache())

    # ── 記事分類 ──────────────────────────────────────
    b_groups   = group_for_b_type(raw_articles)
    b_urls     = {a.url for group in b_groups.values() for a in group}
    c_articles = [a for a in raw_articles if is_c_type(a) and a.url not in b_urls]
    c_urls     = {a.url for a in c_articles}
    a_articles = [a for a in raw_articles if a.url not in b_urls and a.url not in c_urls]

    print(f"A型: {len(a_articles)} / B型: {len(b_groups)}トピック / C型: {len(c_articles)}")

    # ── タスク構築 ─────────────────────────────────────
    # (prompt, article_type, primary_raw, progressive_phase, progressive_target_slug)
    tasks_payload: list[tuple[str, str, RawArticle, Optional[int], Optional[str]]] = []

    # A型速報
    for a in a_articles:
        tasks_payload.append((build_a_type_prompt(a), "A型速報", a, None, None))

    # B型（Progressive判定あり）
    for topic, group in b_groups.items():
        next_phase, existing_slug = determine_progressive_phase(topic, prog_cache)
        if next_phase and existing_slug:
            # 既存記事あり → Progressive更新
            existing_body = prog_cache[topic].get("body_preview", "")
            prompt = build_progressive_update_prompt(group, topic, next_phase, existing_body)
            tasks_payload.append((prompt, "B型深掘り", group[0], next_phase, existing_slug))
            print(f"  🔄 Progressive Phase{next_phase} 対象: {topic} → {existing_slug}")
        else:
            # 初回 → 新規B型記事
            tasks_payload.append((build_b_type_prompt(group, topic), "B型深掘り", group[0], None, None))

    # C型（常に新URL）
    for a in c_articles:
        tasks_payload.append((build_c_type_prompt(a), "C型リーク", a, None, None))

    # ── 生成実行 ───────────────────────────────────────
    client = anthropic.AsyncAnthropic()
    sem    = asyncio.Semaphore(MAX_PARALLEL)

    results = await asyncio.gather(*[
        generate_article(client, prompt, atype, raw, sem, prog_phase, prog_slug)
        for prompt, atype, raw, prog_phase, prog_slug in tasks_payload
    ])
    generated = [g for g in results if g is not None]
    print(f"生成完了: {len(generated)} 件")

    # ── Progressive キャッシュ更新 ─────────────────────
    for g in generated:
        topic_key = _topic_key(g.title)
        if not topic_key:
            continue
        if g.progressive_phase:
            # Phase 2/3 更新: フェーズを進める
            register_to_cache(prog_cache, topic_key, g.slug, g.progressive_phase, len(g.body))
        elif g.article_type in ("A型速報", "B型深掘り") and g.is_must_catch:
            # MUST_CATCH の新規記事: Phase 1 として登録
            register_to_cache(prog_cache, topic_key, g.slug, 1, len(g.body))

    save_progressive_cache(prog_cache)
    print(f"Progressive キャッシュ更新: {len(prog_cache)} トピック")

    # ── 出力 ───────────────────────────────────────────
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for g in generated:
            f.write(json.dumps(asdict(g), ensure_ascii=False) + "\n")
    print(f"出力: {OUTPUT_PATH}")

    # ── サマリー ──────────────────────────────────────
    a_count    = sum(1 for g in generated if g.article_type == "A型速報")
    b_new      = sum(1 for g in generated if g.article_type == "B型深掘り" and g.progressive_phase is None)
    b_prog     = sum(1 for g in generated if g.article_type == "B型深掘り" and g.progressive_phase is not None)
    c_count    = sum(1 for g in generated if g.article_type == "C型リーク")
    print(f"\n  A型速報: {a_count}件 / B型新規: {b_new}件 / B型Progressive更新: {b_prog}件 / C型: {c_count}件")


if __name__ == "__main__":
    asyncio.run(main())
