# Tech Gear Guide — プロジェクト全方針・決定事項

> 作成日: 2026-04-24 / 最終更新: 2026-04-25（Progressive×Discovery設計確定・DBスキーマ追記）  
> ステータス: 方針確定・開発準備中

---

## 1. メディア基本情報

| 項目 | 内容 |
|---|---|
| **サイト名** | Tech Gear Guide |
| **ドメイン** | techgearguide.jp 等（取得予定・未確定） |
| **コンセプト** | 海外権威メディアの情報を正確に伝え、専門家視点の示唆を加える日本語テックメディア |
| **ターゲット読者** | テックリテラシー高めの日本人（20〜40代）|
| **競合参考サイト** | tech-gadget.reinforz.co.jp（記事フォーマットのみ参考、他は独自） |
| **運営** | Reinforz Insight |

---

## 2. 取り扱いジャンル・カテゴリ

優先5ジャンル（記事配分の重点）：

```
ニュース（速報）
├── 【最重要】スマートフォン（iPhone / iOS / Android / Galaxy / Pixel / Xiaomi）
├── 【最重要】タブレット（iPad / iPad Pro / Galaxy Tab / Surface / Pixel Tablet）
├── 【最重要】Windows（OS / PC / Surface / Copilot+ PC / Windows Update）
├── 【最重要】CPU・GPU・チップ（NVIDIA / AMD / Intel / Apple Silicon / Qualcomm）
├── 【最重要】AI（ChatGPT / Gemini / Copilot / Claude / Llama / LLM全般）
├── XR・AR・VR（Apple Vision Pro / Meta Quest / AR Glasses）
├── ウェアラブル（Apple Watch / Galaxy Watch / AirPods / Pixel Watch）
└── その他（アプリ・周辺機器・ガジェット）
```

### カテゴリ別1日あたり記事数目安

| カテゴリ | 目安本数 | 備考 |
|---|---|---|
| スマートフォン | 15〜18本 | iPhone・Android速報が主力 |
| AI | 8〜10本 | 最も伸び率が高いジャンル |
| CPU・GPU | 8〜10本 | 発表時期に増減 |
| Windows | 6〜8本 | OS・PC・Surface |
| タブレット | 4〜6本 | iPad・Galaxy Tab・Surface |
| XR・AR・VR | 3〜5本 | Vision Pro・Meta Quest・ARグラス |
| ウェアラブル | 3〜5本 | Apple Watch・Galaxy Watch・AirPods |
| その他 | 3〜5本 | アプリ・ガジェット |
| **合計** | **~55本** | |

---

## 3. 記事方針・品質ルール

### 3-1. 記事タイプ（3種）

| タイプ | 文字数 | 内容 | 1日の本数目標 |
|---|---|---|---|
| **A型・速報** | 1,500〜2,000字 | 海外1〜2ソースの要点＋専門解説 | 35〜40本 |
| **B型・深掘り** | 1,500〜2,000字 | 複数ソース統合・業界背景・日本市場への影響 | 5〜8本 |
| **C型・リーク噂** | 1,500〜2,000字 | 次世代機の噂＋ソース信頼度評価＋確度表示 | 5〜8本 |

**1日合計目標: 50記事**

### 3-2. 記事構成

- **見出し数**: H2を3〜5個（可変）。**見出し内容は元記事のトピックに応じてAIが自由に設定**すること。「事実→背景→日本市場への影響→今後の展開」の固定パターンは禁止。毎回同じ構造になるとAI生成感が強まりユーザー離れにつながる
- **文字数**: 1,500〜2,000字を目標。ただし元記事が短い場合は無理に水増しせず、品質を優先して柔軟化
- **語調**: **です・ます調**（だ・である調は使用禁止）
- **見出し直下サマリー**: 情報量が多い見出しの直後に、箇条書きまたはテーブルで要点をまとめる形式を**時折**使う。全見出しに使うのではなく、自然に効果的な箇所のみ
- **日本市場への言及**: 日本発売・円換算・キャリア対応等は記事の性質上関連がある場合のみ言及。**全記事で日本セクションを設けることはしない**（AI生成感・単調さを避けるため）
- **出典**: 必ずURL付きで記載（最低2本）
- **リード文**: 冒頭に2〜3行（見出しなし）

### 3-3. 記事フォーマット（テンプレート）

```markdown
---
title: [SEO最適化タイトル]
slug: [url-slug]
category: [カテゴリ名]
tags: [タグ1, タグ2, タグ3]
article_type: A型速報 | B型深掘り | C型リーク
source_reliability: ★〜★★★★★  ← C型のみ
published_at: [ISO8601]
---

[リード文 2〜3行：何が起きたかを凝縮]

## [元記事の内容から自然に導かれる見出し1]

<!-- 必要に応じて見出し直下に箇条書きやテーブルで要点をまとめる（時折） -->
- 要点1
- 要点2

[本文（です・ます調）]

## [元記事の内容から自然に導かれる見出し2]

[本文（です・ます調）]

## [元記事の内容から自然に導かれる見出し3]

[本文（です・ます調）]

<!-- H2は3〜5個で元記事のトピックに合わせて自由に設定。下記は一例 -->
<!-- ❌ 毎回「日本市場への影響」「今後の展開」を入れない -->
<!-- ✅ 競合比較・技術詳細・発売情報・価格・業界背景など内容次第で決める -->

---

**出典**
- [記事タイトル](URL) — メディア名
- [記事タイトル](URL) — メディア名
```

### 3-4. 品質ルール（厳守事項）

**必須:**
- ソース記事の事実を正確に伝える（数字・スペック・日付はソース通り）
- ソース信頼度の明示（"Bloombergが報道" vs "リーカー情報"）
- 専門的示唆を含める（なぜ重要か・業界へのインパクト・日本ユーザーへの意味）
- 出典URLを全記事に最低2本必ず記載

**禁止:**
- ソースにない情報の捏造（ハルシネーション絶対禁止）
- 推測をファクトとして記述
- 出典なしの記事投稿
- 翻訳だけの薄い記事（示唆・解説が必須）

### 3-5. C型リーク記事の信頼度表示

| 確度 | 対象 |
|---|---|
| ★★★★★ | Mark Gurman（Bloomberg）、Zac Bowden（Windows Central） |
| ★★★★☆ | 9to5Mac / 9to5Google 独自情報 |
| ★★★☆☆ | 著名リーカー（@OnLeaks、Ice Universe等） |
| ★★☆☆☆ | 匿名ソース・未確認情報 |
| ★☆☆☆☆ | Reddit・SNS上の未確認リーク |

---

## 4. ニュースソース設計

### 4-1. スマホ系

| Tier | ソース | 強み |
|---|---|---|
| 1 | The Verge | 総合テック最高権威 |
| 1 | 9to5Mac | iPhone速報の決定版 |
| 1 | 9to5Google | Pixel/Android最速 |
| 1 | Android Authority | Samsung/Xiaomi幅広い |
| 1 | GSMArena | スペック・レビュー |
| 1 | Bloomberg Technology | Gurman情報・産業動向 |
| 2 | MacRumors | iPhone噂・リーク |
| 2 | PhoneArena | 比較レビュー |
| 2 | XDA Developers | 技術深掘り |
| 2 | TechRadar | 総合ガジェット |
| 2 | Engadget | トレンド・実用 |
| 2 | NotebookCheck | リーク最速・ベンチマーク |
| 3 | Reddit r/Android | バズ検知 |
| 3 | Reddit r/iphone | バズ検知 |
| 3 | Reddit r/GooglePixel | バズ検知 |

### 4-2. Windows系

| Tier | ソース | 強み |
|---|---|---|
| 1 | Windows Central | Windows専門No.1 |
| 1 | Ars Technica | 技術深掘り・信頼性高 |
| 2 | Neowin | Windows速報 |
| 2 | Thurrott | Microsoftエコシステム |
| 3 | Reddit r/Windows11 | バズ検知 |
| 3 | Reddit r/Surface | バズ検知 |

### 4-3. CPU・GPU・チップ系

| Tier | ソース | 強み |
|---|---|---|
| 1 | Tom's Hardware | CPU/GPU最重要メディア |
| 1 | Ars Technica | チップ・半導体深掘り |
| 2 | Wccftech | GPU/CPUリーク |
| 2 | VideoCardz | GPU専門 |
| 2 | NotebookCheck | ラップトップ・チップ性能 |
| 3 | Reddit r/hardware | バズ検知 |
| 3 | Reddit r/AMD | バズ検知 |
| 3 | Reddit r/nvidia | バズ検知 |

### 4-4. AI系

| Tier | ソース | 強み |
|---|---|---|
| 1 | The Verge AI | OpenAI / Google / Meta AI最速報道 |
| 1 | Ars Technica | LLM・研究論文の深掘り |
| 2 | VentureBeat AI | スタートアップ・産業AI |
| 2 | TechCrunch AI | 調達・事業動向 |

**RSSフィード候補:**
- The Verge: https://www.theverge.com/rss/index.xml（全カテゴリ、AIキーワードフィルタ）
- VentureBeat AI: https://venturebeat.com/category/ai/feed/
- TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/feed/

### 4-5. 産業・ビジネス系（権威性向上）

| Tier | ソース | 強み |
|---|---|---|
| 1 | Reuters Technology | ファクト重視の速報 |
| 1 | Financial Times Tech | 産業・企業動向 |
| 2 | The Information | 内部情報・調査報道 |

### 4-5. 著名リーカー監視（SNS/RSS）

**スマホ:**
- Mark Gurman (@markgurman) — Apple最高信頼度
- Ice Universe (@UniverseIce) — Samsung
- @OnLeaks (Steve Hemmerstoffer) — 3Dレンダリング
- Yogesh Brar (@heyitsyogesh) — インド発Android情報

**Windows:**
- WalkingCat (@_h0x0d_) — Microsoft内部リーク
- Zac Bowden (Windows Central) — Microsoft公式筋

---

## 5. 著者方針

### 方針: 「Tech Gear Guide編集部」方式（架空ライター不使用）

**理由:**
- Googleの現行方針ではAIコンテンツ自体は問題ないが、AIを人間と偽ることはペナルティリスク
- 架空ライターは2024年以降ペナルティ増加傾向
- 編集部方式＋透明性強化でE-E-A-Tを確保する方が長期的に安全

### E-E-A-T強化策

- **Aboutページ**: 海外20社以上を常時モニタリングする編集方針を明記
- **編集方針ページ**: 情報精度最優先・ソース確認プロセス・誤報訂正フローを記載
- **AIアシスト明示**: 各記事に "AI支援により作成" の一行を入れる（信頼性シグナル）
- **運営会社の透明性**: Reinforz Insightとの関係を明示
- **出典の徹底**: 全記事に出典URLを必ず記載（信頼性の担保）

---

## 6. 技術スタック

| レイヤー | 技術 | 理由 |
|---|---|---|
| **フロントエンド** | Next.js 16 (App Router) | SEO・ISR対応・既存プロジェクトと統一 |
| **UI** | shadcn/ui | 既存プロジェクトと統一 |
| **データベース** | Supabase（Postgres） | 無料枠で十分・成長に耐えられる |
| **画像ストレージ** | Supabase Storage | 記事アイキャッチ画像の保管 |
| **ホスティング** | Vercel | Next.jsとの相性最良・ISR対応 |
| **CMS** | なし（パイプライン直接投稿） | WordPressは使用しない |
| **パイプライン** | Python（SmaTechから改造） | 既存資産の流用 |
| **自動化** | GitHub Actions（Cron） | 1日3回自動実行 |

### WordPressを使用しない理由

- ISRによる高速な記事更新が可能
- Next.js + Supabaseでフルコントロール
- 1日50記事の大量投稿に対応できる柔軟性
- Core Web Vitals最適化がWordPressより容易

---

## 7. Supabaseデータベース設計方針

### 基本テーブル（Phase 1）

```sql
articles
├── id (uuid, PK)
├── title (text)
├── slug (text, unique)
├── body (text)  -- Markdown本文
├── category (text)
├── tags (text[])
├── article_type (text)  -- A型/B型/C型
├── source_reliability (int)  -- C型のみ 1〜5
├── sources (jsonb)  -- [{title, url, media}]
├── featured_image_url (text)
├── seo_description (text)
├── published_at (timestamptz)
├── created_at (timestamptz)
├── last_major_update_at (timestamptz)  -- Progressive大型更新時に更新
├── progressive_phase (int)             -- 1=速報 / 2=詳細 / 3=決定版（null=通常記事）
├── is_published (bool)
├── is_must_catch (bool)
└── is_leak (bool)
```

---

## 8. コンテンツ生成パイプライン設計

### SmaTechからの差分

| 項目 | SmaTech | Tech Gear Guide |
|---|---|---|
| sources.yaml | スマホのみ | スマホ＋Windows＋CPU/GPU追加 |
| generate.py | 翻訳＋要約中心 | 専門示唆＋信頼度評価＋FAQ＋H2×4固定 |
| publish.py | WordPress REST API | Supabase REST API（INSERT） |
| 記事タイプ | A型・B型 | A型・B型・C型（リーク） |
| 文字数 | 800〜3,000字（タイプにより異なる） | 1,500〜2,000字目標（元記事が短い場合は柔軟化） |
| 見出し数 | 2〜4個（可変） | H2×3〜5個（可変・AIっぽさ回避） |
| 画像処理 | WP メディアアップロード | Supabase Storage |
| 自動化 | 手動実行 | GitHub Actions Cron（1日3回） |

### パイプラインフロー

```
[GitHub Actions Cron: 7時・12時・18時]
        ↓
collect.py
  └── 全ソースRSS/Reddit収集
  └── フィルタリング・重複排除
  └── スコアリング（Tier・リーク・重要度）
        ↓
generate.py
  └── A型: 上位記事をスコア順に生成（40本）
  └── B型: 同一トピック複数ソースを統合（5本）
  └── C型: リークキーワード検出記事を生成（5本）
  └── Claude API (claude-sonnet-4-6)
        ↓
publish.py（Supabase版）
  └── OGP画像取得 → Supabase Storage保存
  └── Supabase articles テーブルにINSERT（新URL）or UPDATE（Progressive更新）
  └── Next.js ISR revalidate トリガー
  └── Sitemap ping（C型/MUST_CATCH新記事・Progressive大型更新時のみ）
```

### Claude API コスト試算

```
1記事: 約2,500 output tokens
50記事/日: 125,000 output tokens
費用: $0.38/日 ≒ ¥55/日 ≒ ¥1,650/月
（入力トークン含め ¥3,000〜4,000/月 想定）
```

---

## 9. SEO戦略

### 技術SEO

- Core Web Vitals 最適化（LCP < 2.5秒）
- 構造化データ（NewsArticle / BreadcrumbList / FAQPage）
- XMLサイトマップ自動生成
- canonical URL
- Google News 申請・登録
- robots.txt 適切設定

### コンテンツSEO

- タイトル: デバイス名＋モデル番号＋年号（例:「iPhone 17 Pro スペック判明【2026年】」）
- メタdescription: 150字以内で要点凝縮
- H2×3〜5の論理的構造（ソース量・記事タイプに応じて可変）
- 内部リンク（同一デバイスシリーズ記事を自動リンク）
- タイトルパターン: 「〜が判明」「〜を確認」「〜の可能性」「〜とは？」

---

## 10. AIO（AI検索最適化）戦略

ChatGPT / Perplexity / Google AI Overviews に引用されるための設計：

1. **事実の密度を高める** — 数字・日付・スペック・価格を明確に記述
2. **問いへの直接回答構造** — 検索意図に即答するリード文
3. **FAQセクション** — 各記事末尾に3〜5問のQ&A（将来実装）
4. **出典の透明性** — 「Bloomberg の Mark Gurman が報告」のような出典明記
5. **E-E-A-T シグナル** — 編集方針・About・Privacy Policy の充実
6. **エンティティ最適化** — デバイス名・モデル番号・メーカー名を正確に記述

---

## 11. Google Discovery戦略

Discoveryはキーワードではなく**興味グラフとビジュアル**で流入する：

**必須要件:**
- アイキャッチ画像: 1,200×628px以上（高品質）
- タイトル: 好奇心を刺激する（「〜が判明」「〜の衝撃スペック」「〜が激変」）
- 新鮮さ: 公開後30分以内にインデックス（ISR活用）
- Google News 登録済みサイト

**流入増加施策:**
- 話題のデバイス（iPhone次世代・Galaxy新作）は即日記事化
- サムネイルに実機画像を使用（OGP取得 or 公式プレスイメージ）
- CTR × セッション時間の最大化（記事導入で読者を引きつける）
- 1日10本以上の更新頻度維持（50本で理想的）
- **Sitemap ping**: C型/MUST_CATCH新記事公開時・Progressive大型更新時にGoogleへpingを送信（`/api/revalidate` と並行実行）

---

## 12. マネタイズ戦略（3フェーズ）

### Phase 1: 記事蓄積期（0〜3ヶ月）

- **目標**: 記事4,000本・月間10万PV
- **収益源**: Google AdSense（10万PV到達で申請）
- **DB活用**: 記事保存のみ

### Phase 2: SEO流入期（3〜6ヶ月）

- **目標**: 月間50万PV（Discovery＋organic流入）
- **収益源追加**:
  - Amazonアフィリエイト（デバイス紹介記事に自動挿入）
  - A8.net / もしもアフィリエイト
  - AdSense収益目標: 月¥3〜10万
- **DB追加機能**:
  - PVトラッキング（人気記事分析）
  - 内部リンク自動生成（関連記事）

### Phase 3: 収益最大化期（6ヶ月〜）

- **目標**: 月間200万PV
- **収益源追加**:
  - プレスリリース掲載（¥30,000〜/本）
  - 記事スポンサーシップ（メーカー向け）
  - 有料ニュースレター（週次サマリー）
  - 売却・M&A（高PVメディアの市場価値活用）
- **DB追加機能**:
  - ユーザー行動分析
  - Search Console連携・SEOギャップ分析
  - トレンド自動検出→記事優先度制御

---

## 13. DB×成長戦略

```
Phase 1 articles テーブルのみ
  ↓
Phase 2 page_views テーブル追加
         popular_articles ビュー
         related_articles（内部リンク自動生成）
  ↓
Phase 3 user_sessions テーブル
         keywords テーブル（Search Console連携）
         trending_topics（トレンド自動検出）
```

DBデータを活用した改善サイクル：
- カテゴリ別PV → どのジャンルを増量すべきか判断
- 記事公開時間 vs Discovery流入 → 最適投稿時刻を特定
- タイトルパターン分析 → CTR高いタイトル型をプロンプトに反映
- リーク記事 vs 通常記事の収益差 → C型記事の増減判断

---

## 14. コンテンツ鮮度維持・流入減衰対策

### 根本原因
速報記事のみで構成すると、デバイス世代交代時に関連記事が一括で陳腐化し、流入が急落する。Googleのフレッシュネスアルゴリズムはニュース系記事を3〜6ヶ月で大幅に評価を落とす。

### 対策1: コンテンツポートフォリオ設計（最重要）

| タイプ | 比率 | 寿命 | 内容 |
|---|---|---|---|
| 速報ニュース | 70% | 1〜7日 | Discovery流入の主力 |
| デバイスまとめ（継続更新） | 15% | 恒久 | ハブ記事・随時更新 |
| エバーグリーン | 15% | 1〜3年 | 「使い方」「選び方」「比較」 |

エバーグリーンは速報50本/日とは別に**週5〜10本**追加生成する。

### 対策2: ハブ＆スポーク構造

```
[ハブ記事: 継続更新型]
「iPhone 17 Pro 全情報まとめ【随時更新】」
  ↑ すべての速報スポーク記事が内部リンクで流れ込む

[スポーク記事: 個別速報]
- 「iPhone 17 Pro カメラ判明」
- 「iPhone 17 Pro 価格リーク」
→ 全てハブ記事にリンク
```

新スポーク記事公開時にハブ記事の`updated_at`を自動更新 → Googleがフレッシュと判定し続ける。

### 対策3: 記事自動リフレッシュシステム

Supabaseのview_countで減衰を検知し、週次バッチで自動リフレッシュ：
- 前週比50%以下に落ちた記事をリフレッシュキューに投入
- 「〜速報」→「〜完全まとめ【2026年最新版】」に変換
- 同一URLのまま更新 → 被リンク・URL資産を保持

### 対策4: デバイスライフサイクル対応コンテンツシフト

```
発表前（噂期）  → C型リーク記事 → Discovery流入先行
発表直後       → A型速報大量投入 → Discovery爆発
発売1ヶ月後    → B型深掘りに移行 → SEO長尾流入
発売3ヶ月後    → まとめ・比較記事 → エバーグリーン化
次世代発表直前 → 「今買うべきか」記事 → 購買検討層
```

### 対策5: 年間カレンダー型コンテンツ計画

```
1月: CES（PC・GPU発表ラッシュ）
2月: MWC（スマホ・モバイル）、Samsung Unpacked
5月: Google I/O
6月: WWDC（iOS/macOS発表）
9月: Apple iPhone発表
10月: Google Pixel発表
11月: Black Friday（「今が買い時」記事）
12月: 年間まとめ・次年度予測
```

各イベント2週間前からソース監視を強化し、ハブ記事を先行作成。

### 対策6: メールマガジン（アルゴリズム非依存の流入）

- 週次ニュースレター「Tech Gear Guide週刊まとめ」
- beehiiv or Resend で実装
- 1,000人規模でも固定直接流入として機能
- Googleアルゴリズム変動への耐性を担保

### 対策7: プラットフォーム分散

| プラットフォーム | 施策 |
|---|---|
| X（Twitter） | 記事自動投稿 → Discovery流入の補完 |
| Google News | 必ず登録・フレッシュネス補完 |
| Pinterest | テック比較画像 → 長期的な流入 |
| RSS/Atom | テック系ユーザー向け購読フィード |

### 対策8: 内部リンク自動管理

新記事公開時に、関連する旧記事に自動で内部リンクを追記。旧記事のPageRankを維持し、検索評価の減衰を緩和。Supabaseのcategory・tags・デバイス名で関連性を判定。

### 対策9: 流入減衰の自動検知ダッシュボード

```
Supabase view_count + Search Console API 連携
→ 前週比50%以下の記事を自動検出
→ リフレッシュキューに自動投入
→ 毎日のパイプライン実行時に同時処理
```

---

## 15. 圧倒的ユーザー価値・SEO1位・Discovery最大化戦略

### 根本方針

「他サイトが物理的に真似できない価値」を設計に埋め込む。日本の競合はほぼ翻訳+要約のみ。Tech Gear Guideはそこに10の次元で差をつける。

### 戦略1: 速報パイプラインの革新（15〜30分公開）

```
[現在想定: GitHub Actions 3回/日] → 最大8時間遅延

[Tech Gear Guide実装]
常駐Pythonプロセス（5分ごとRSSポーリング）
  ↓
Priority Queue:
  CRITICAL（発表・リーク）→ 15分以内に公開
  HIGH（スペック・価格）  → 30分以内に公開
  NORMAL（通常ニュース）  → Cron 3回/日

実装: VPS or Railway.appで常駐プロセス運用
GitHub ActionsはNORMAL記事専用に降格
```

### 戦略2: Progressive Article（最大の差別化・他サイトがやっていない）

同一URL・同一スラッグが時間と共に進化する：

```
T+15分  Phase 1: ミニ速報（600〜800字）
         事実のみ。🔴 LIVEバッジ表示。

T+2〜6時間 Phase 2: 詳細記事（1,500〜2,000字）
         複数ソース統合。日本市場への影響。技術詳細。

T+24〜48時間 Phase 3: 決定版（2,000〜2,500字）
         全情報統合。比較表。FAQ。今後の予測。
         「最終更新: ○月○日 ○時」明示。
```

**なぜ最強か:**
- SEO: 1つのURLにシグナルが集積（被リンク・滞在時間・PV）
- Discovery: 速報で配信 → 詳細化で再配信の機会
- AIO: 最終的に最も包括的 → ChatGPT/Perplexityに引用される
- ユーザー: 「ここに戻れば常に最新」というブランド定着

#### Progressive Article × Discovery流入のハイブリッド設計（確定）

> **懸念**: Progressive（同URL更新）は新URL数が減り、Discovery流入チャンスが減るのでは？
>
> **結論**: 実設計上の影響は小さい。1日50記事のうちProgressiveが適用されるのは多くて5〜10件程度であり、大多数の記事は新URLで発行される。ただしC型/MUST_CATCHは明示的に新URL固定とする。

| 記事タイプ | URL発行方針 | 理由 |
|---|---|---|
| **A型速報** | 新URL発行 | Discovery流入を毎日最大化 |
| **B型深掘り（続報）** | Progressive更新（同URL） | SEOシグナル集積・ユーザーUX |
| **C型リーク / MUST_CATCH** | **必ず新URL発行** | 大型ニュースのDiscovery流入を確実に確保 |

**Sitemapによる更新通知（Progressive更新時）**:
Progressive更新が発生したとき、Sitemapの `lastmod` を更新してGoogleにpingを送ることで再クロール・再評価を促す。

```python
# publish.py に追加
async def ping_sitemap(sitemap_url: str):
    """Sitemap更新をGoogleに通知"""
    async with httpx.AsyncClient(timeout=10) as c:
        await c.get(f"https://www.google.com/ping?sitemap={sitemap_url}")
```

大型更新（文字数が前版の1.5倍以上増加）の場合にのみpingを送る。細かい修正では送らない。

### 戦略3: 日本向け独自価値（唯一無二の情報）

| 独自要素 | 内容 | 実装 |
|---|---|---|
| JPY自動換算 | 価格は必ず円換算（為替API連携） | Python |
| 日本発売日 | 日本での発売日・入手可否を必ず調査 | プロンプト指示 |
| キャリア対応 | ドコモ・au・ソフトバンク・楽天対応状況 | プロンプト指示 |
| 技適・周波数 | 日本バンド対応（SIMフリー購入判断） | プロンプト指示 |
| 日本版の差異 | グローバル版と日本版の仕様差 | プロンプト指示 |

### 戦略4: 記事の7層品質構造

```
レイヤー1: 事実の正確な報告（基本）
レイヤー2: なぜ重要か（業界文脈）
レイヤー3: 日本市場への影響（独自価値）
レイヤー4: 技術的深掘り（専門性）
レイヤー5: 前世代・競合との比較（判断支援）
レイヤー6: 今後の予測（付加価値）
レイヤー7: FAQ（AIO対策 + 検索意図カバレッジ）
```

**比較表の自動生成**: Supabaseにスペックデータベースを持ち、記事生成時に自動挿入。

**ソース信頼度の可視化**: C型に限らず全記事でソース信頼度を★で表示。

### 戦略5: アイキャッチ画像の自動取得・生成（方針確定）

**著作権クリアを最優先**とし、以下の2段階で取得する。元記事のOGP画像の無断転用は行わない。

#### Step 1: メーカー公式プレスルーム画像（最優先）

報道・プレス利用を明示的に許可している公式サイトから画像を取得。

| キーワード | プレスルーム |
|---|---|
| iphone / ipad / mac / apple | Apple Newsroom (apple.com/newsroom) |
| galaxy / samsung | Samsung Newsroom (news.samsung.com) |
| rtx / geforce / nvidia | NVIDIA Press (nvidianews.nvidia.com) |
| radeon / ryzen / amd / expo | AMD Newsroom (amd.com/en/newsroom) |
| windows / surface / microsoft | Microsoft News (news.microsoft.com) |
| pixel / google | Google Blog (blog.google) |
| openai / chatgpt | OpenAI News (openai.com/news) |
| snapdragon / qualcomm | Qualcomm News (news.qualcomm.com) |

記事タイトルのキーワードから対象プレスルームを特定 → httpxでog:image取得 → 画像ダウンロード。

#### Step 2: Unsplash API（Step 1失敗時の代替）

商用利用無料・著作権完全クリア。カテゴリ別キーワードで検索。

| カテゴリ | 検索キーワード例 |
|---|---|
| smartphone | smartphone closeup / mobile phone |
| tablet | tablet device / ipad |
| windows | laptop windows / computer screen |
| cpu_gpu | computer chip / gpu graphics card |
| ai | artificial intelligence / neural network |
| xr | virtual reality headset / ar glasses |
| wearable | smartwatch / wearable technology |
| general | technology / electronics |

#### 共通後処理（Pillow）

```
取得画像 → リサイズ 1,200×628px → Tech Gear Guideロゴオーバーレイ → カテゴリバッジ貼付
→ Supabase Storage に保存 → articles.featured_image_url に記録
```

**クレジット表記**: Unsplash使用時は記事末尾に `Photo by [Author] on Unsplash` を自動挿入。

### 戦略6: SEO1位設計

**Top Storiesカルーセル（Google検索最上部）:**
- Google News Publisher Center 登録
- NewsArticle構造化データ（dateModified必須）
- Progressive Articleの更新のたびにdateModifiedが変わる → 継続的に配信対象

**Featured Snippets（位置0）:**
- ハウツー記事は番号付きリスト・箇条書きを使用
- 最初の200字で質問への直接回答を配置

**People Also Ask（PAA）:**
- 全記事末尾にFAQセクション（3〜5問）
- FAQPageスキーマを実装
- PAAボックスの独占を狙う

### 戦略7: タイトル設計の公式

```
速報系:
「[デバイス名] [具体的事実]が[判明/確定/流出]【[ソース名]報道】」
→ iPhone 17 Proのカメラ仕様が全て判明【Bloomberg報道】

リーク系:
「[デバイス名]のレンダリング画像が流出—[衝撃的変更点]」
→ iPhone 17のデザインが流出—カメラバンプが消えた

日本向け:
「[デバイス名]の日本価格・発売日が判明—[円換算]から」
→ Galaxy S26 Ultraの日本価格が判明—前モデルより¥15,000値下がり

エバーグリーン:
「[デバイス名]の[機能名]を最大限活かす[N]の方法【2026年版】」
```

### 戦略8: ユーザー定着設計

| 機能 | 効果 | 実装 |
|---|---|---|
| PWAプッシュ通知 | 速報をリアルタイム配信 → 直接流入 | Next.js PWA |
| デバイス追跡機能 | 特定デバイスの最新情報をフォロー | Supabase |
| 週次メルマガ | アルゴリズム非依存の直接流入 | beehiiv or Resend |
| カテゴリ別RSSフィード | テック系ユーザーの購読 | Next.js API Route |

### 戦略9: データ蓄積による参入障壁

時間が経つほど価値が上がる資産を構築：

```
benchmarks テーブル:
  GeekbenchスコアをDB化 → 「歴代チップベンチマーク比較」記事

specs テーブル:
  全デバイスのスペックをDB化 → 「スペック比較ページ」

prices テーブル:
  価格推移をDB化 → 「値下がり予測・買い時判断」記事

→ 競合が後から追いつこうとしても蓄積の時間差がある
→ 参入障壁になる
```

### 戦略10: 記事の「面白さ」最大化（v2追加）

日本語テックメディアの最大の問題は「翻訳して終わり」で思考が止まっていること。
Tech Gear Guideは以下の原則で差をつける。

#### 原則1: 「So what?」を自然に加える（必須化しない）

事実に加えて「それが読者にとって何を意味するか」を、**記事の内容上自然に加えられる場合のみ**入れる。全記事で無理に入れるとAI生成感が出るため、馴染まない記事では省略する。

```
加えられる例:
「新チップは3nmプロセスを採用しており、前世代より消費電力が約30%下がる計算です。
同じバッテリー容量でも体感できるほど長く使えるようになります」

加えなくてよい例:
速報性が重要なニュースで、示唆を書くほどの情報量がない場合
```

#### 原則2: 数値を「体感できる言葉」に翻訳する

| 技術数値 | 体感翻訳の例 |
|---|---|
| RAM 4GB増加 | 4K動画の同時編集がスムーズになります |
| バッテリー容量10%増 | 1日の充電が1回から0.8回に近づきます |
| CPU性能20%向上 | 重い写真編集ソフトの処理が体感できるほど速くなります |
| ストレージ読み込み速度2倍 | OSの起動やアプリ起動が数秒単位で短縮されます |

#### 原則3: 読者の「見えない疑問」を先読みして答える

読者が心の中で思っているが質問しない疑問：
- 「なぜ今この発表なのか」（競合への対抗？決算前のアピール？）
- 「競合と実質何が違うのか」
- 「自分は買い換えるべきか」
- 「日本ではいつ・いくらで買えるのか」

これらを記事中で先回りして答えることで、読者が「この記事で全部わかった」と感じる体験を作る。

#### 原則4: 読者アクション提案

記事の性質に応じて「判断できる一文」を末尾に入れる。

```
発売済み製品 → 「購入を検討するなら〜がポイントです」
発表済み未発売 → 「発売まで待つ価値があるかどうかは〜次第です」
更新系       → 「〜の環境では即適用推奨 / 様子を見た方がよい更新です」
リーク系     → 「現時点では〜と判断するのが妥当です。続報を待ちましょう」
```

#### 原則5: FAQセクション（AIO対策）

記事末尾に2〜3問のQ&Aを追加。ChatGPT・Perplexity・Google AI Overviewsへの引用を狙う。
質問は「読者が実際にGoogle検索するキーワード」ベースで設計する。

#### 原則6: 業界の文脈を読む

単独のニュースに見えても、背後には競争・戦略・市場動向がある。
- AMDがEXPO更新 → IntelがXMP強化したタイミングに合わせた対抗
- Appleが価格維持 → インフレ下でのポジショニング戦略
- OpenAIが新機能 → Microsoftとの資本関係・競合Googleへの対抗

これを「業界の裏読み」として1〜2文添えるだけで記事の深みが増す。

---

### 全体方程式

```
速報性（15分以内）
  × Progressive Article（記事が成長する）
  × 日本独自価値（円換算・日本発売・キャリア対応）
  × 7層品質構造（比較表・信頼度・FAQ・予測）
  × SEO設計（Top Stories・Featured Snippet・PAA）
  × Discovery最適化（OGP動的生成・タイトル公式）
  × ユーザー定着（PWA通知・メルマガ・RSS）
  × データ蓄積（スペックDB・ベンチマークDB）
  × 鮮度維持（ハブ記事・エバーグリーン・リフレッシュ）

= 日本最高のテックデバイスメディア
```

---

## 16. 全文取得戦略（確定）

> 2026-04-25 検証完了。15ソース全て全文取得可能を確認。

### 基本方針

**全ソースの全文取得を必須とする。** RSSサマリーのみから記事生成するとハルシネーションが発生するため禁止。
ソーステキストが500字未満の場合は記事生成をスキップ（品質担保）。

### 4段階フェッチ戦略（優先順）

```
Step 1: RSS本文（高速・無負荷）
Step 2: httpx直接フェッチ（ブラウザUA偽装）
Step 3: Jina Reader API（https://r.jina.ai/{url}）
Step 4: Playwright ヘッドレスブラウザ（playwright-stealth使用）
```

各ステップで500字以上取得できたら以降はスキップ。

### ソース別フェッチ戦略（テスト結果確定）

| ソース | 主要手法 | 備考 |
|---|---|---|
| MacRumors | RSS直接 | RSSに全文入り |
| Android Authority | httpx直接 | 200 OK・全文取得可 |
| GSMArena | httpx直接 | 200 OK・全文取得可 |
| Engadget | httpx直接 | 200 OK・全文取得可 |
| Wccftech | httpx直接 | 200 OK・6,256字確認 |
| XDA Developers | Jina Reader | httpx 403のためJina経由 |
| NotebookCheck | Jina Reader | httpx 403のためJina経由 |
| Ars Technica | Jina Reader | httpx Cloudflare回避のためJina |
| 9to5Mac | Playwright(stealth) | Jina 451エラー → Playwright |
| 9to5Google | Playwright(stealth) | Jina 451エラー → Playwright |
| Windows Central | Playwright(stealth) | 8,815字確認 |
| Tom's Hardware | Playwright(stealth) | 6,133字確認 |
| TechRadar | Playwright(stealth) | 7,579字確認 |
| VideoCardz | Playwright(stealth) | RSS 403のためgooglenewsdecoder必須 |
| Neowin | Playwright(stealth) | RSS 403のためgooglenewsdecoder必須 |

### VideoCardz / Neowin の URL取得方法

RSSフィードが403を返すため、Google News RSSを `googlenewsdecoder` パッケージでデコードして元記事URLを取得する。

```python
from googlenewsdecoder import gnewsdecoder
result = gnewsdecoder(google_news_url, interval=1)
article_url = result.get("decoded_url", "")
# → https://videocardz.com/newz/[slug] 等が得られる
```

### Playwright使用時の設定

```python
# playwright-stealth + domcontentloaded + 追加待機
wait_until = "domcontentloaded"
wait_for_timeout = 3000  # ms
# Cloudflare challenge検出時は追加5秒待機
# セレクタ優先順: article > .article-body > .post-content > main > body
```

### 品質チェック閾値

| テキスト長 | 判定 | 処理 |
|---|---|---|
| 2,000字以上 | 全文取得 ✅ | 記事生成へ |
| 500〜1,999字 | 部分取得 ⚠️ | 生成可（文字数を柔軟化） |
| 500字未満 | 取得不可 ❌ | 記事生成スキップ |

---

## 17. 収集ルール（確定）

### 17-1. 対象記事の基本条件

| 条件 | 内容 |
|---|---|
| **公開時刻** | 収集時点から **24時間以内** に公開された記事のみ対象 |
| **言語** | 英語記事（日本語生成はgenerate.pyが担当） |
| **本文長** | ソーステキスト500字以上でなければ生成スキップ |
| **実行回数** | 1日3回（7時・12時・18時の GitHub Actions Cron） |

### 17-2. 重複防止ルール（最重要）

同一ニュースを複数記事にしないための3層チェック：

```
Layer 1: URL完全一致チェック
  → 同じURLは同一バッチ内・前バッチでも絶対に2回処理しない
  → 処理済みURLを processed_urls.json にキャッシュ（最新48時間分保持）

Layer 2: タイトルフィンガープリント
  → 記号・空白・大小文字を除いた文字列で一致チェック
  → 例: "RTX 5090 specs leak!" ≒ "rtx5090specsleak"
  → 同一フィンガープリントが既存なら高スコア側を残してスキップ

Layer 3: 主要キーワード重複チェック
  → 同一バッチ内で同じデバイス名×同じ情報タイプ（スペック/価格/リーク）が重複しないか確認
  → 例: 「iPhone 17 Pro スペック」記事が3本あれば最高スコアの1本のみ採用
```

### 17-3. 主要製品・キーワード監視（MUST_CATCH）

以下のキーワードを含む記事は **絶対に取りこぼさない**。スコアに+15の優先ボーナスを付与。

```python
MUST_CATCH_KEYWORDS = {
    "smartphone": [
        "iphone 17", "iphone 18", "iphone ultra",
        "galaxy s26", "galaxy z fold 7", "galaxy z flip 7",
        "pixel 10", "pixel 9a",
        "oneplus 13", "xiaomi 15",
    ],
    "tablet": [
        "ipad pro", "ipad air", "ipad mini",
        "galaxy tab s10", "galaxy tab s11",
        "surface pro 12", "surface pro 11",
        "pixel tablet 2",
    ],
    "windows": [
        "windows 12", "windows 11 update",
        "copilot+ pc", "surface pro", "surface laptop",
        "recall", "windows update",
    ],
    "cpu_gpu": [
        "rtx 5090", "rtx 5080", "rtx 6000",
        "rx 9070", "rx 9080",
        "ryzen 9 9000", "core ultra 300",
        "apple m5", "apple m4", "snapdragon x elite", "snapdragon 8 gen 4",
    ],
    "ai": [
        "gpt-5", "gpt-6", "openai",
        "gemini 2.5", "gemini 3",
        "claude 4", "claude opus",
        "llama 4", "llama 5",
        "copilot", "google deepmind",
        "sora 2", "veo 3",
    ],
}
```

### 17-4. リーク・噂の優先処理

リークキーワードを含む記事は MUST_CATCH と同様に優先スコア +5。

```python
LEAK_KEYWORDS = [
    "leak", "leaked", "exclusive", "rumor", "rumoured",
    "insider", "source", "allegedly", "reportedly",
    "dummy unit", "hands-on", "render", "concept",
    "benchmark", "geekbench", "antutu",
]
```

### 17-5. カテゴリ別1バッチあたり上限

記事が集中しすぎるカテゴリの上限（1バッチ＝1/3日分）:

| カテゴリ | 上限本数/バッチ | 理由 |
|---|---|---|
| smartphone | 7本 | 1日21本まで → 最多カテゴリ |
| ai | 4本 | 1日12本まで |
| cpu_gpu | 4本 | 発表ラッシュ時の集中防止 |
| windows | 3本 | 1日9本まで |
| tablet | 2本 | 1日6本まで |
| xr | 2本 | 発表イベント時に増加 |
| wearable | 2本 | 新製品シーズンに増加 |
| general | 2本 | 補完用 |

ただし **MUST_CATCHフラグの記事は上限を無視して必ず収録**。

---

## 18. 未決定事項（要確認）

- [ ] ドメイン取得（devicebrief.com 等を調査・確保）
- [ ] Vercel or Xserver ホスティング選定
- [ ] Supabaseプロジェクト新規作成 or 既存流用
- [ ] GitHub Actions の実行スケジュール最終確定（7時・12時・18時 案）
- [ ] Google News 申請タイミング（記事50本以上が目安）
- [ ] AdSense 申請タイミング（10万PV到達後）
