# -*- coding: utf-8 -*-
"""
Tech Gear Guide — generate.py
collected_articles.jsonl → Claude API → generated_articles.jsonl
"""

import asyncio
import io
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODEL                  = "claude-sonnet-4-6"
MAX_PARALLEL           = 5
INPUT_PATH             = Path("collected_articles.jsonl")
OUTPUT_PATH            = Path("generated_articles.jsonl")
PROGRESSIVE_CACHE_PATH = Path("progressive_slugs_cache.json")
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
    published_at: str
    is_must_catch: bool
    is_leak: bool
    original_score: float
    source_names: str
    progressive_phase: Optional[int] = None
    progressive_target_slug: Optional[str] = None

# ─────────────────────────────────────────────
# Progressive キャッシュ管理
# ─────────────────────────────────────────────

def load_progressive_cache() -> dict:
    if not PROGRESSIVE_CACHE_PATH.exists():
        return {}
    with open(PROGRESSIVE_CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_progressive_cache(cache: dict):
    with open(PROGRESSIVE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def _purge_expired_cache(cache: dict) -> dict:
    now    = datetime.now(timezone.utc)
    active = {}
    for key, entry in cache.items():
        try:
            published = datetime.fromisoformat(entry["published_at"])
            if (now - published).total_seconds() / 3600 <= PROGRESSIVE_CACHE_TTL_H:
                active[key] = entry
        except Exception:
            pass
    return active

def determine_progressive_phase(topic_key: str, cache: dict) -> tuple[Optional[int], Optional[str]]:
    entry = cache.get(topic_key)
    if not entry:
        return None, None
    current_phase = entry.get("phase", 1)
    if current_phase >= 3:
        return None, None
    return current_phase + 1, entry["slug"]

def register_to_cache(cache: dict, topic_key: str, slug: str, phase: int, body_len: int):
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
    "iphone 17", "iphone 18", "galaxy s26", "galaxy z fold 7",
    "rtx 5090", "rtx 5080", "rx 9070", "apple m5",
    "windows 12", "surface pro 12",
    "gpt-5", "gemini 2.5", "claude 4", "pixel 10",
    "apple vision pro 2", "meta quest 4",
    "apple watch series 11", "galaxy watch 8",
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
あなたはTech Gear Guideの上級編集者です。
海外テックメディアの記事を日本人読者向けに翻訳・解説する専門家です。

【絶対ルール】
1. ソーステキストにある情報のみを使う（ハルシネーション禁止）
2. 数字・スペック・日付・価格はソース通りに記載（改変禁止）
3. ソースにない情報を推測で補わない
4. 語調は必ずです・ます調（だ・である調は文末で使用禁止）
5. 記事末尾に必ず「## 出典」セクションを設け、`- **メディア名** — [記事タイトル](URL)` の形式で記載する（メディア名・タイトル・URLの3点セット必須）
6. 発売日・発表日・リリース日などの年号はソース記事の記載を厳守する
   （例：ソースが2026年と書いているなら2026年と記載。絶対に1年ずらさない）
7. 今回のソース記事に書かれていない別の製品・別のニュースへの言及を禁止する
   （「同日に〜が報じられた」「同じく〜も発表」等のバッチ内汚染は厳禁）
8. ソース信頼度スコア（X/5、★☆等）は記事本文に一切記載しない
9. 不確定表現の断定変換を禁止する
   ソースの「may」「might」「reportedly」「allegedly」「up to」「as many as」は
   必ず「〜の可能性があります」「〜と報じられています」「最大〜」等の不確定表現で訳す
10. 数値の限定詞（最大・最小・最大で・約）はソース通りに維持する
    「up to 60%」→「60%」（最大なし）への変換は誤り
11. ソースの否定・未確認表現は必ず否定のまま訳す
    「not confirmed」→「確認されていません」（「確認された」への変換は誤り）
    「denied」→「否定されています」
12. 鉤括弧「」を使った直接引用はソースに実在する表現のみ許可する
    ソースに該当する発言・引用がない場合は間接引用にする
13. 通貨換算はソースに円換算が記載されている場合のみ行う
    ソースが「$1,599」の場合は「1,599ドル（約23万円）」のような換算は禁止。
    ドル表記のままにすること（ただし円換算はあくまで補足として添える場合はWARN対象だが禁止ではない）
14. タイトルに「判明」「確定」「決定」「明らか」を使うのは一次情報（メーカー公式発表）のみ
    リーク・ダミー機・APK解析・匿名情報源に基づく記事のタイトルでは使用禁止。
    代わりに「可能性」「示唆」「か」「報道」等の不確定表現を使うこと
15. 情報の主語・適用範囲を正確に書く（範囲の拡大禁止）
    ソースが「スタートメニュー」の話をしているなら「スタートメニュー」と書く（「Windows 11のUI全体」に拡大しない）
    ソースが「Proモデル」の話をしているなら「Proモデル」と書く（「ラインナップ全体」に拡大しない）
    ソースが「AIインフラ向けCPU需要」の話をしているなら「半導体市場全体」と書かない
16. 情報源の伝達経路を正確に書く
    ソースAがソースBを引用している場合は「BがAを引用するかたちで伝えた」と書く
    APK解析・内部テスト画像・Telegramリーク等の場合は、その種類（一次情報でないこと）を読者に伝える
    例: 「Android Authorityが、アプリ内の未公開UIを解析した情報として報じた」
17. 極端な%表示（1000%以上）は表現を言い換える
    例: 「予想比3,000%超過」は誤解を招く。「予想0.01ドルに対し0.29ドルを達成」等の実数表現に変える
18. ソース内のネガティブ情報（リスク・逆風・課題・懸念）を省略しない
    ソースが「好材料」と「悪材料」の両方を述べている場合、どちらも記事に含める
    例: 決算が好調でも、CFOが逆風として挙げた項目は必ず触れる
    例: 製品の強化点を書くなら、価格上昇・互換性の問題等の課題も書く
19. 複数の相反する情報がある場合は両論を書く
    ソースが「別の情報源では〜とも言われている」と書いている場合、記事でも対立を明示する
    例: 「本体厚8.75mmとの測定結果だが、別のリーク情報では8.8mmとの説もある」
    「一方で」「ただし別の報告では」等の表現で対立を示す
20. 企業向け・管理者向け機能を一般向けとして書かない
    ソースで「managed device」「enterprise」「IT管理者」「MDM」「Group Policy」向けと
    説明されている機能は、記事でも対象範囲を正確に書く
    誰でも使える機能のように書くのは不正確
21. 情報源の種類（ダミー機・APK解析・Telegram・匿名情報源等）を明記する
    ダミー機の測定 → 「量産品と形状が異なる場合もあるダミー機を使った比較」と書く
    APK解析 → 「アプリの未公開コードを解析した情報として」と書く
    Telegram/匿名リーク → 「非公式の情報源からのリーク」と書く
22. 複数要因による結果を単一要因に帰属させない
    ソースが複数の原因を挙げている場合、記事でも複数要因を列挙する
    例: 粗利改善の要因が「在庫販売・販売量・価格・ミックス・歩留まり」なら全部書く
    「〜だけが原因」「〜のみによって」という書き方は禁止

23. 情報源の階層を正確に書く（★必須）
    ソース記事（Tom's Hardware・TechRadar等のメディア）が企業の公式発表を
    「解釈・推定・計算」した内容と、企業が直接述べた内容を明確に区別すること。
    NG: 「TSMCは演算トランジスタが48倍になると述べた」
        → Tom's HardwareがTSMCロードマップを基に計算した値を「TSMC発言」にしてはいけない
    OK: 「Tom's Hardwareは、TSMCロードマップを基に演算トランジスタが最大48倍になると報じている」
    NG: 「○○社はサプライチェーン攻撃として認めた」
        → ソースメディアがそう解釈・表現したに過ぎない場合は「○○と（メディア名）は報じている」

24. 数量の単位をソース通りに書く
    ソースが「records」「entries」（レコード件数）と書いている場合、
    「顧客数」「ユーザー数」「人数」に変換しない。
    例: 「8.7 million records」→「870万件のレコード」（○）
                               →「875万人の顧客」（✗ 単位が変わっている）
    1件のレコードが1人に対応するとは限らない。

25. メディアの評価語は帰属を明示する
    ソースメディアが「矮小化」「過小評価」「事実上の撤退」等の評価語を使っている場合、
    それをそのまま事実として書かず、必ず「（メディア名）は〜と報じている」と帰属を明示する。
    NG: 「○○社は事件を大幅に矮小化した」（事実として断定）
    OK: 「TechRadarは、○○社の説明は事件の規模を大幅に矮小化していると報じている」

26. ソース記事のメタ情報を本文に記載しない（★絶対禁止）
    生成記事の本文・見出し・FAQ・まとめのいずれにも、以下の情報を絶対に記載しない:
    - 著者名・媒体内カテゴリ名（例: 「Brady Snyder氏（Android Authority）」「Features」）
    - ソース記事の文字数・語数（例: 「約1,338語（英語）」「約1,200字」）
    - 「関連キーワード:」「記事URL:」「公開日:」等のメタデータ形式の表記
    これらはパイプライン内部の管理情報であり、読者向け記事に掲載するものではない。
    著者への言及が必要な場合は「（媒体名）によると」の形式で媒体名のみ記載する。

27. アナリスト・リーク情報源の主張は必ず帰属表現で書く（★誇張禁止）
    情報源が「アナリストの観測」「リーク」「匿名情報源」「サプライチェーン観測」の場合：
    - 主語は必ず「○○氏は〜と主張した」「○○が〜と報じている」「〜の可能性がある」とする
    - 「開発中」「参加」「確定した」等の断定形は絶対に使わない
    NG: 「OpenAIがMediaTek・Qualcommとチップを開発中」
    OK: 「Ming-Chi Kuo氏は、OpenAIがMediaTek・QualcommとAI向けチップを開発している可能性を指摘した」
    NG: 「Luxshareが製造パートナーとして参加」
    OK: 「Luxshareが製造パートナーとして関与しているとKuo氏は報告している」

28. タイトル・リードの主張強度をソース強度と一致させる
    ソースが「可能性」「示唆」「観測」のレベルなら、タイトルも「か」「可能性」「示唆」にとどめる。
    NG: 「アイコンが消える日——OpenAIが2028年量産目標のスマートフォンを開発中」（断定的）
    OK: 「OpenAIがAIエージェント中心のスマホを検討か——Kuo氏が2028年量産・MediaTek関与を報告」
    NG: 「安いのに上位機に勝つ」（無条件）
    OK: 「Pixel 10aはPixel 10より実用面で優れる点も——4つの理由をAndroid Authorityが指摘」

29. 条件付き比較を無条件化しない
    ソースが「X点でAがBを上回る」と言っている場合、「AがBより優れる」とは書かない。
    必ず何の点で上回るのかを明示し、総合比較のような印象を与えない。
    NG: 「Pixel 10aがPixel 10を超える」「上位機に勝つ」
    OK: 「バッテリー容量・軽量性・物理SIMトレイなど実用面4点でPixel 10aが優位」
    レビュアーが挙げた具体的な比較ポイントがソースに明記されているなら、それをそのまま書く。

30. レビュアーの主観・評価を事実として書かない
    ソースがレビュー記事（実機レポート・比較記事）の場合、評価はレビュアーの主観である。
    NG: 「Pixel 10aは『退屈で地味』だが上位機を上回ることが実機で証明された」
    OK: 「Brady Snyder氏は、Pixel 10aは地味だが実用面でPixel 10を上回る点があると評価している」
    「証明」「実証」という語はソースで実験・定量測定がなされた場合のみ使う。

31. 「ゼロ」「完全」「すべて」等の絶対語はソース通りのみ使う
    ソースにない絶対語・完全語を生成で加えると誇張になる。
    NG: 「アプリ切り替えストレスをゼロにする」（ソースにない）
    OK: 「アプリ切り替えの手間を大幅に減らす」
    NG: 「完全に無料で使える」（無料範囲が限定的な場合）
    OK: 「一部のコンテンツを無料で利用できる」

32. 企業・サービスの戦略・意図の推測は推測であることを明示する
    ソースに書かれていないビジネス戦略・企業意図の解釈を追加する場合、
    必ず「と読める」「と考えられる」「との見方もある」等の推測語を付ける。
    NG: 「無料層を囲い込みPremium課金へ誘導する狙いがある」（Spotifyは明言していない）
    OK: 「無料層の取り込みと有料転換の両立を狙っていると読める」
    NG: 「MediaTekとQualcommの両社が同時に名指しされているのは役割分担の可能性がある」（ソース外推測）
    OK: 「両社が名指しされている理由は現時点では不明だ」

33. ソースにない詳細・具体例を独自補完しない
    ソースが「4つの理由」と言っているだけで個別の理由が書かれていない場合、
    その内容を推測・一般知識で補って書いてはいけない。
    NG: Q&Aで「個別内容はメタデータに含まれていない」と書くほど内容が不明なのに、
        本文でそれらしい説明を書いてしまっている矛盾
    OK: ソースに書かれていない詳細は書かず、「詳細は出典元を参照」と誘導する
    特に「なぜ〜なのか」「どのような仕組みか」の説明は、ソースに記述がある場合のみ記載する。

34. タイトルで数字を宣言したら本文でその数を必ず明示する（★最重要）
    タイトル・リードに「N個」「N点」「Nつ」「N選」「Nポイント」「N理由」「N項目」等の
    数字を含む場合、本文の中でその数だけ内容を箇条書きまたはH2見出しで明示すること。
    NG: 「4つのポイントを実機で評価」というタイトルなのに、本文でポイントを列挙していない
    OK: タイトルで「4つ」と宣言 → 本文に①〜④の見出しや箇条書きでポイントを4つ明示する
    ソースに個別の内容が書かれていない場合はルール33に従いタイトルも数字を含まない形にする。
    「4つのポイント」→「複数のポイント」に変更するか、ソースから読み取れる内容のみで構成する。

35. ソースの具体情報（数値・専門家名・コメント・固有名詞・引用）を必ず記事に含める（★必須）
    ソース記事に以下が含まれている場合は、必ず記事本文に盛り込むこと：
    - 具体的な数値（重量・容量・サイズ・価格・スペック）
      例: Pixel 10aが183g、Pixel 10が204g、バッテリーが5,100mAh vs 4,970mAh
    - 専門家・レビュアーの名前と所属（例: Brady Snyder氏（Android Authority））
      ただし記事本文には媒体名のみ「（Android Authorityによると）」と記載すること（ルール26）
    - 固有名詞（製品名・企業名・モデル名・サービス名）
    - 直接引用文がソースにある場合は鉤括弧で引用する（ルール12の範囲内で）
    これらを省略して抽象的な記事にすることは品質基準違反。具体性が記事価値の源泉。

36. 地域限定情報は必ず適用範囲を明記する
    ソースで「米国版のみ」「特定市場向け」「一部の地域では」と限定されている情報は、
    記事でも「〜は米国版のみの仕様です」「〜は一部の地域に限られます」と明記すること。
    NG: 「物理SIMトレイを搭載している」（米国版のみなのに全モデルのように書く）
    OK: 「物理SIMトレイは米国版モデルのみの仕様です」
    日本向けメディアとして、日本市場への影響・対応状況も合わせて述べること（ソースに記載がある場合）。

37. 競合・比較対象の仕様は正確にウェブ検索・既知情報と照合する
    比較記事でApple・Google・Samsung等の競合製品の仕様を述べる場合、
    ソースの記述が最新の公式仕様と一致しているか注意すること。
    例: 「Apple Fitness+はApple Watch必須」は現在は誤り（iPhone単体でも利用可能）
    ソース記事が古い情報に基づいて競合を説明している場合は、
    「ソース記事では〜と記載されているが、現行仕様は異なる可能性がある」と注記すること。

【文体ルール】
- 文末は「〜です」「〜ます」「〜しています」「〜されています」
- 「〜だ」「〜である」単体での文末は禁止
- 読者に語りかける自然な文体を心がける
- 「なお、」「また、」「さらに、」の多用はAIっぽくなるので控える

【ユーザー価値の原則】
- 事実を伝えるだけでなく「それが読者にとって何を意味するか」を、自然に加えられる場合は加える
- 数値が出てきたら、体感できる言葉に翻訳できる場合は翻訳する
- 読者が「なぜ今なのか」「競合と何が違うのか」と疑問に思いそうな場合は先回りして答える

【記事の面白さを上げるコツ】
- 業界の「裏にある動き」を読む（競合関係・市場シェア・タイミングの意味）
- 「前回の予測と今回の情報の違い」があれば指摘する
- 技術的な内容は「ユーザー体験にどう変わるか」に落とす

【出典メディアの埋め込み】
ソース記事にYouTube動画URL・X（旧Twitter）投稿URLが含まれており、
本文に関連して読者が見ると価値がある場合は、該当箇所の直後に
URLを単独行（前後に空行あり）として記載してください。
マークダウンリンク（[テキスト](URL)）ではなく生URLのみを記載すること。
例:
　発表動画はこちらです。

　https://www.youtube.com/watch?v=xxxxxxx

　上記の動画では…
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
- 【ダミー機・リーク情報の扱い】ダミー機（dummy unit/mock）からの測定値・外観情報は
  「最終製品と異なる場合があります」を必ず添える。「〜であることが判明した」ではなく
  「〜との測定結果が報じられています」と書く
- 複数のリークで数値が割れている場合（例: 本体厚8.75mm説と8.8mm説）は
  「〜という測定結果がある一方、別のリーク情報では〜とも報じられています」と両論を書く
- 搭載が「噂段階」のスペック（RAM・センサー・機能）は「予定」「確定」ではなく
  「搭載が噂されています」「複数のリーク情報が示しています」と書く
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
- 【重要】機能の対象範囲を正確に書く: 企業・管理者向け（MDM/Group Policy/managed device対象）の機能は
  「企業のIT管理者向け」と明記する。一般ユーザーが使える機能として誤解させない
- 「〜が可能になりました」と書く前に、対象デバイス・バージョン・ユーザー種別を確認する
""",
    "cpu_gpu": """\
【CPU・GPU記事の深掘り指示】
- ベンチマーク数値は「実際のゲームや作業でどう変わるか」に翻訳する
- 価格帯・コストパフォーマンスの観点を入れる（ソースに情報があれば）
- IntelvsAMD、NVIDIAvsAMDの競争文脈を踏まえた解説を入れる
- 「誰が買うべき製品か」（ゲーマー／クリエイター／一般ユーザー）を示す
- 【決算・業績記事の注意】利益率・売上が好調な場合でも、CFO・CEOが言及したリスク・逆風
  （材料費・歩留まり・PC需要・競合動向）を必ず書く。好材料だけ書くと不正確
- 【決算・業績記事の注意】利益改善の原因が複数ある場合（在庫販売・価格・ミックス・歩留まり等）、
  代表的な要因を列挙する。単一要因に絞り込まない
- 在庫販売・ビニング（選別・再分類）・de-spec製品に関する記事では、
  「スクラップ同然」のような誇張表現を使わず、CFO・公式説明の言葉（de-spec/shelved product等）
  をベースに書く
""",
    "ai": """\
【AI記事の深掘り指示】
- 機能を「具体的な使用シーン」で説明する（抽象的な能力説明ではなく）
- 競合AI（ChatGPT/Gemini/Claude/Copilot）との実質的な違いを示す
- 「無料プランで使えるか」「日本語は自然か」は読者の最重要関心事なので必ず触れる
- プライバシー・データ利用ポリシーの変化があれば指摘する
- 【重要】プラットフォームを正確に書く:
  ソースがAndroid版の話をしているならAndroid版と書く（Web版・iOS版への展開は「不明」と書く）
  ソースがWeb版の話をしているなら「ブラウザ版」と書く。全プラットフォームに拡大しない
- APK解析・未公開UI発見の場合は「アプリの未公開コードを解析した情報」と明記し、
  「公式発表済み」のような書き方はしない。リリースされない可能性があることも触れる
- 無料プラン・有料プランの区別がソースで不明な場合は「不明」と書き、
  推測で「無料プランでも使えます」等は書かない
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

ACTION_GUIDE = """\
【記事末尾の読者アクション提案】
記事の内容に応じて、以下のいずれかを自然な形で末尾近くに入れる（馴染まない記事では省略可）:
- 製品が発売済み → 「購入を検討するなら〜がポイントです」
- 製品が発表済み・未発売 → 「発売まで待つ価値があるかどうかは〜次第です」
- アップデート系 → 「〜の環境では即座に適用すべき/慎重に様子を見た方がよい更新です」
- リーク系 → 「現時点では〜と判断するのが妥当です。続報を待ちましょう」
"""

FAQ_GUIDE = """\
【FAQセクションについて】
記事末尾の出典の前に、2〜3問のQ&Aを入れる。AIO対策と読者の疑問解消が目的。

フォーマット:
## Q&A

**Q. [読者が最も聞きたいこと]**
[簡潔な回答。1〜3文]

**Q. [2番目に多そうな疑問]**
[回答]

スペック詳細・価格比較・使い方系の記事にのみ追加し、短いニュース記事では省略可。
"""

PRE_WRITE_CHECKLIST = """\
【執筆前に必ず確認（記事を書き始める前に頭の中でチェック）】

★ 具体情報の引き継ぎ（最重要・最初に確認）
□ ソース記事にある具体的な数値（重量・バッテリー容量・価格・スペック・パーセンテージ）をリストアップした
  例: Pixel 10aが183g、Pixel 10が204g、バッテリー5,100mAh vs 4,970mAh → これらを記事本文に必ず含める
□ ソースに専門家・アナリスト・レビュアーのコメントがある場合、その要旨を記事に含める
  （媒体名のみで引用: 「Android Authorityによると〜」）
□ ソースに直接引用文がある場合、鉤括弧で引用する（ソースに実在する文言のみ）
□ タイトルで「N個/N点/Nつ/N選/Nポイント/N理由」と数を宣言する場合、本文でその数を箇条書き・H2で明示する
  例: 「4つのポイント」→ ① フラット背面デザイン ② 183g（軽量） ③ 5,100mAh ④ 物理SIM（米国版のみ）と明示
  ソースに内容が書かれていない場合はタイトルに数字を入れない（「複数の優位点」等に変更）
□ ソースが地域限定（米国版のみ・特定地域向け等）の情報を含む場合、記事でも「〜は米国版のみ」と明記する

★ 事実の正確性
□ ソース記事の発売日・発表日の年号を確認した（20XX年が正しいか）
□ ソースに「may」「reportedly」「up to」「leaked」等の不確定表現があれば把握した
□ ソースに「not confirmed」「denied」等の否定表現があれば把握した
□ 今回のソース記事に登場しない別製品・別ニュースには言及しない
□ タイトルに「判明」「確定」を使う場合は公式発表ベースか確認した（リーク・ダミー機・APK解析の場合は不可）

★ 範囲・帰属の正確性
□ ソースが言及している対象の範囲を拡大していないか確認した
□ ソースがさらに別のソースを引用している場合、帰属先（via 元メディア名）を記事内に明記する
□ ソースがリスク・逆風・課題を挙げている場合、記事でも触れた（ポジティブだけ書いていない）
□ 同じトピックで相反する情報がある場合、両方の情報を「一方で〜という説もある」等で書いた
□ 企業・管理者向け機能を一般向けとして書いていない（「managed device向け」等の表記確認）
□ 情報源がダミー機・APK解析・Telegramの場合、その種類と限界を本文内に明記した
□ 複数要因による結果を単一要因に絞り込んでいない
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

【具体情報の必須引き継ぎ ★執筆の最優先事項】
ソース記事に含まれる以下の情報は、必ず記事本文に含めること。省略・抽象化は品質基準違反。
- 具体的な数値: 重量(g)・バッテリー容量(mAh)・スペック・価格・パーセンテージ・サイズ(mm)等
- 固有名詞: 製品名・モデル名・企業名・サービス名・チップ名
- 専門家・アナリスト・レビュアーのコメントや評価（媒体名のみで引用）
- 直接引用文（ソースに実在する文言のみ鉤括弧で）
- 比較数値（例: A=183g vs B=204g のように両方を数値で対比）
タイトルで「N個/N点/Nつ」と数を宣言した場合は、本文でその数を番号付きで明示すること。

【見出し設計の原則】
- 見出しの内容は元記事のトピックを読み込んで自由に設定する
- 「事実→背景→日本市場→今後の展開」の固定パターンは禁止
- 記事ごとに自然な構成を作る

{deep_dive}

{ACTION_GUIDE}

{FAQ_GUIDE}

{PRE_WRITE_CHECKLIST}

【出力フォーマット（必ずこの形式で出力）】
---META---
title: [SEOタイトル・日本語・70字以内。具体的な数値・製品名を入れると強い]
slug: [英数字ハイフン区切り]
category: {a.category}  ← この値をそのまま出力すること（変更禁止）
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: A型速報
seo_description: [150字以内。検索意図に直接回答する内容]
---END_META---

[リード文：2〜3行。です・ます調]

## [見出し1]
[本文]

## [見出し2]
[本文]

## [見出し3]
[本文]

## 出典
- **{a.source_name}** — [{a.title}]({a.url})

---
【ソース記事本文（参照用）】
{a.body[:6000]}
"""


def build_b_type_prompt(articles: list[RawArticle], topic: str) -> str:
    sources_block = "\n\n".join(
        f"【ソース{i+1}: {a.source_name}】\n{a.body[:2500]}"
        for i, a in enumerate(articles[:5])
    )
    sources_citations = "\n".join(
        f"- [{a.title}]({a.url}) — {a.source_name}"
        for a in articles[:5]
    )
    primary   = articles[0]
    deep_dive = CATEGORY_DEEP_DIVE.get(primary.category, CATEGORY_DEEP_DIVE["general"])

    return f"""\
以下の複数ソースを統合してB型深掘り記事を作成してください。

【記事仕様】
- 記事タイプ: B型深掘り
- トピック: {topic}
- 目標文字数: 1,800〜2,500字
- 見出し数: H2を4〜5個
- 語調: です・ます調

【具体情報の必須引き継ぎ ★執筆の最優先事項】
各ソースに含まれる以下の情報は、必ず記事本文に含めること。省略・抽象化は品質基準違反。
- 具体的な数値: 重量・容量・スペック・価格・パーセンテージ等（ソース間で値が異なる場合は両方を記載）
- 固有名詞: 製品名・企業名・モデル名・サービス名・チップ名
- アナリスト・専門家・レビュアーのコメント（媒体名のみで引用）
- 直接引用文（ソースに実在する文言のみ鉤括弧で）
タイトルで「N個/N点/Nつ」と数を宣言した場合は、本文でその数を番号付きで明示すること。

【B型記事の原則】
- 複数ソースを「並べる」のではなく「統合して一つの深い解説」にする
- 各ソースの見解が異なる部分は明記する
- 単独ソースでは見えない「全体像」を読者に見せることがB型の価値

{deep_dive}

{ACTION_GUIDE}

{FAQ_GUIDE}

{PRE_WRITE_CHECKLIST}

【B型記事特有の注意】
- ソース間で数値・スペックが異なる場合は「ソース1では〜、ソース2では〜と報じられています」と明記し、どちらかに断定しない
- ソース同士を組み合わせてソースが明示していない新しい結論を導かない

【出力フォーマット】
---META---
title: [SEOタイトル・日本語・70字以内]
slug: [英数字ハイフン区切り]
category: {primary.category}  ← この値をそのまま出力すること（変更禁止）
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: B型深掘り
seo_description: [150字以内]
---END_META---

[リード文：2〜3行]

## [見出し1]
...

## 出典
{sources_citations}

---
【ソース記事本文（参照用）】
{sources_block}
"""


def build_progressive_update_prompt(
    articles: list[RawArticle],
    topic: str,
    target_phase: int,
    existing_body: str,
) -> str:
    phase_label  = {2: "詳細版（Phase 2）", 3: "決定版（Phase 3）"}.get(target_phase, f"Phase {target_phase}")
    target_chars = {2: "1,800〜2,500字", 3: "2,200〜3,000字"}.get(target_phase, "2,000字以上")
    sources_block = "\n\n".join(
        f"【新ソース{i+1}: {a.source_name}】\n{a.body[:2500]}"
        for i, a in enumerate(articles[:5])
    )
    sources_citations = "\n".join(
        f"- [{a.title}]({a.url}) — {a.source_name}"
        for a in articles[:5]
    )
    primary   = articles[0]
    deep_dive = CATEGORY_DEEP_DIVE.get(primary.category, CATEGORY_DEEP_DIVE["general"])
    today     = datetime.now().strftime("%Y年%m月%d日")

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
- 記事冒頭に「最終更新: {today}」を含める

{deep_dive}

{FAQ_GUIDE}

【出力フォーマット（slugは既存のものを必ず引き継ぐ）】
---META---
title: [SEOタイトル（情報量が増えた場合は更新可）]
slug: [既存記事と同じslug]
category: {primary.category}  ← この値をそのまま出力すること（変更禁止）
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: B型深掘り
seo_description: [150字以内・更新後の内容を反映]
---END_META---

> **最終更新: {today}**

[リード文]

## [見出し1]
...

## 出典
{sources_citations}

---
【既存記事の本文（参照用）】
{existing_body[:3000]}

【新しいソース情報（参照用）】
{sources_block}
"""


def build_c_type_prompt(a: RawArticle) -> str:
    return f"""\
以下のリーク・噂記事をC型リーク記事にしてください。

【記事仕様】
- 記事タイプ: C型リーク
- 目標文字数: 1,500〜2,000字
- 見出し数: H2を3〜5個
- 語調: です・ます調

【具体情報の必須引き継ぎ ★執筆の最優先事項】
ソース記事に含まれる以下の情報は、必ず記事本文に含めること。省略・抽象化は品質基準違反。
- 具体的な数値: 重量・容量・スペック・価格・パーセンテージ・発売予定年月等
- 固有名詞: 製品名・企業名・モデル名・チップ名・情報源の人物名（媒体名として引用）
- アナリスト・専門家のコメント（「○○氏によると〜」の形で）
- 直接引用文（ソースに実在する文言のみ鉤括弧で）

【C型記事の原則】
- 確定情報とリーク情報を文中で必ず区別する
  確定: 「〜が確認されています」「〜と発表されました」
  リーク: 「〜と報告されています」「〜の可能性があります」
- ソースの信頼性の根拠（過去の的中率・情報入手経路）を必ず解説する
- 「このリーク情報が正確だった場合、何が起きるか」の分析を加える
- 情報源の種類を記事内で読者に明示する:
  ダミー機 → 「量産品と異なる場合があるダミー機を使った測定」
  APK解析 → 「アプリの未公開コードを解析した情報として」
  Telegram/匿名 → 「非公式の情報源からのリーク情報として」
  via引用 → 「〜がXXを引用するかたちで報じた」
- 同じトピックで複数の相反するリークがある場合は必ず両論書く
  「一方で〜という別の情報もある」「情報は一致していない」等で対立を示す
- ダミー機・APK由来の情報には「最終製品の仕様は変わる可能性があります」を必ず入れる
- タイトルで「判明」「確定」「正式」は絶対に使わない。「か」「可能性」「リーク」を使う

{ACTION_GUIDE}

{FAQ_GUIDE}

{PRE_WRITE_CHECKLIST}

【出力フォーマット】
---META---
title: [SEOタイトル・「〜リーク」「〜流出」等・70字以内]
slug: [英数字ハイフン区切り]
category: {a.category}  ← この値をそのまま出力すること（変更禁止）
tags: [タグ1, タグ2, タグ3, タグ4]
article_type: C型リーク
seo_description: [150字以内]
---END_META---

[リード文：2〜3行]

## [見出し1]
...

## 出典
- **{a.source_name}** — [{a.title}]({a.url})

---
【ソース記事本文（参照用）】
{a.body[:6000]}
"""

# ─────────────────────────────────────────────
# メタデータパース
# ─────────────────────────────────────────────

VALID_CATEGORIES = {"smartphone", "windows", "cpu_gpu", "ai", "tablet", "general", "xr", "wearable"}

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
# Claude API呼び出し
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
                print(f"  ⚠️  生成失敗（本文不足）: {raw.title[:50]}")
                return None

            slug = progressive_target_slug if progressive_target_slug else meta.get("slug", raw.url_hash)

            parsed_cat = meta.get("category", raw.category)
            if parsed_cat not in VALID_CATEGORIES:
                parsed_cat = raw.category if raw.category in VALID_CATEGORIES else "general"

            return GeneratedArticle(
                title=meta.get("title", raw.title),
                slug=slug,
                category=parsed_cat,
                tags=parse_tags(meta.get("tags", "")),
                article_type=article_type,
                body=body,
                seo_description=meta.get("seo_description", ""),
                sources=[{"title": raw.title, "url": raw.url, "media": raw.source_name}],
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max",    type=int, default=None, help="生成上限（スコア上位N件に絞る）")
    parser.add_argument("--offset", type=int, default=0,    help="先頭N件をスキップして生成（補充用）")
    args = parser.parse_args()

    if not INPUT_PATH.exists():
        print(f"入力ファイルが見つかりません: {INPUT_PATH}")
        return

    raw_articles: list[RawArticle] = []
    with open(INPUT_PATH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            raw_articles.append(RawArticle(**{k: d[k] for k in RawArticle.__dataclass_fields__}))

    if args.offset:
        raw_articles = raw_articles[args.offset:]
    if args.max:
        raw_articles = raw_articles[:args.max]

    print(f"入力: {len(raw_articles)} 件")

    prog_cache = _purge_expired_cache(load_progressive_cache())

    b_groups   = group_for_b_type(raw_articles)
    b_urls     = {a.url for group in b_groups.values() for a in group}
    c_articles = [a for a in raw_articles if is_c_type(a) and a.url not in b_urls]
    c_urls     = {a.url for a in c_articles}
    a_articles = [a for a in raw_articles if a.url not in b_urls and a.url not in c_urls]

    print(f"A型: {len(a_articles)} / B型: {len(b_groups)}トピック / C型: {len(c_articles)}")

    tasks_payload: list[tuple[str, str, RawArticle, Optional[int], Optional[str]]] = []

    for a in a_articles:
        tasks_payload.append((build_a_type_prompt(a), "A型速報", a, None, None))

    for topic, group in b_groups.items():
        next_phase, existing_slug = determine_progressive_phase(topic, prog_cache)
        if next_phase and existing_slug:
            existing_body = prog_cache[topic].get("body_preview", "")
            prompt = build_progressive_update_prompt(group, topic, next_phase, existing_body)
            tasks_payload.append((prompt, "B型深掘り", group[0], next_phase, existing_slug))
            print(f"  🔄 Progressive Phase{next_phase}: {topic} → {existing_slug}")
        else:
            tasks_payload.append((build_b_type_prompt(group, topic), "B型深掘り", group[0], None, None))

    for a in c_articles:
        tasks_payload.append((build_c_type_prompt(a), "C型リーク", a, None, None))

    client = anthropic.AsyncAnthropic()
    sem    = asyncio.Semaphore(MAX_PARALLEL)

    results = await asyncio.gather(*[
        generate_article(client, prompt, atype, raw, sem, prog_phase, prog_slug)
        for prompt, atype, raw, prog_phase, prog_slug in tasks_payload
    ])
    generated = [g for g in results if g is not None]
    print(f"生成完了: {len(generated)} 件")

    for g in generated:
        topic_key = _topic_key(g.title)
        if not topic_key:
            continue
        if g.progressive_phase:
            register_to_cache(prog_cache, topic_key, g.slug, g.progressive_phase, len(g.body))
        elif g.article_type in ("A型速報", "B型深掘り") and g.is_must_catch:
            register_to_cache(prog_cache, topic_key, g.slug, 1, len(g.body))

    save_progressive_cache(prog_cache)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for g in generated:
            f.write(json.dumps(asdict(g), ensure_ascii=False) + "\n")
    print(f"出力: {OUTPUT_PATH}")

    a_count = sum(1 for g in generated if g.article_type == "A型速報")
    b_new   = sum(1 for g in generated if g.article_type == "B型深掘り" and g.progressive_phase is None)
    b_prog  = sum(1 for g in generated if g.article_type == "B型深掘り" and g.progressive_phase is not None)
    c_count = sum(1 for g in generated if g.article_type == "C型リーク")
    print(f"  A型: {a_count} / B型新規: {b_new} / B型Progressive: {b_prog} / C型: {c_count}")


if __name__ == "__main__":
    asyncio.run(main())
