# DeviceBrief — 事業構想・初期実装フロー概要

> 作成: 2026-04-25  
> 対象: プロジェクト全体像の整理・初期フェーズの実装順序

---

## 1. 事業構想

### コンセプト

**「海外テックメディアの情報を、日本人が本当に知りたい形で届ける」**

日本のテックメディアの大半は翻訳＋要約で終わっている。DeviceBriefはそこに専門家視点の示唆・体感できる数値翻訳・読者の「見えない疑問」への先回り回答を加えることで、同じ一次情報から圧倒的に深い記事を届ける。

### 差別化の軸（他メディアが物理的に真似できない構造）

| 差別化要素 | 内容 |
|---|---|
| **速報性** | 常駐プロセスで15〜30分以内公開（Cron 3回/日とは別軸） |
| **Progressive Article** | 同URLが速報→詳細→決定版へ成長。SEOシグナル集積＋ユーザーが「ここに戻れば最新」 |
| **日本向け独自価値** | 円換算・日本発売日・キャリア対応・技適状況 |
| **7層品質構造** | 事実→文脈→日本影響→技術詳細→比較→予測→FAQ |
| **AIO最適化** | FAQ + 事実密度 + 出典明記でChatGPT/Perplexityへの引用を狙う |
| **データ資産** | スペックDB・ベンチマークDB・価格推移を積み上げ → 参入障壁に |

### ターゲット読者

テックリテラシーが高く、新しいデバイス・AIツールへの関心が高い日本人（20〜40代）。
英語記事を読む手間を省きつつ、「翻訳メディアでは得られない深い示唆」を求める層。

### マネタイズ（3フェーズ）

```
Phase 1（0〜3ヶ月）: 記事4,000本蓄積 → AdSense申請（10万PV目安）
Phase 2（3〜6ヶ月）: Discovery + SEO流入 → Amazon/A8アフィリエイト追加
Phase 3（6ヶ月〜） : スポンサード・プレスリリース・ニュースレター有料化・M&A検討
```

---

## 2. コンテンツパイプライン全体像

```
[ニュースソース 18媒体]
  RSS / httpx / Jina Reader / Playwright(stealth)
          ↓
      collect.py
  ・24時間フィルター
  ・MUST_CATCH優先スコアリング
  ・3層重複排除
  ・カテゴリ別上限
          ↓
  collected_articles.jsonl
          ↓
      generate.py
  ・A型速報（新URL）
  ・B型深掘り（新URL or Progressive更新）
  ・C型リーク（必ず新URL）
  ・progressive_slugs_cache.json でPhase管理
          ↓
  generated_articles.jsonl
          ↓
     audit.py（独立監査）
  ・Phase1: ルールベース（タイトル長・本文字数・H2数・ハルシネーション検出等）
  ・Phase2: AIベース（事実確認・日本語品質）
  ・PASS/WARN/FAILで振り分け
          ↓
     publish.py
  ・新規: INSERT → Supabase articles テーブル
  ・Progressive更新: PATCH（大型更新判定あり）
  ・Supabase Storage に画像アップロード
  ・Next.js ISR revalidate
  ・Sitemap ping（C型/MUST_CATCH・Progressive大型更新時のみ）
          ↓
  [DeviceBrief / Next.js 16 + Supabase + Vercel]
```

### 自動実行スケジュール

| 方式 | 頻度 | 対象 |
|---|---|---|
| GitHub Actions Cron | 1日3回（7時・12時・18時） | 通常記事（A型・B型・C型） |
| 常駐プロセス（VPS） | 5分おきにRSSポーリング | MUST_CATCH・速報のみ即時公開 |

---

## 3. 記事タイプとURL発行ルール

| 記事タイプ | URL | 対象 |
|---|---|---|
| A型速報 | 新URL | 通常の速報記事 |
| B型深掘り（初回） | 新URL | 同トピック3ソース以上・初出 |
| B型続報（Phase 2/3） | 既存URLをPATCH | キャッシュ上に前バージョンがある場合 |
| C型リーク | **必ず新URL** | MUST_CATCH × リークキーワード |
| MUST_CATCH速報 | 新URL | 主要製品の大型ニュース（Discovery確保） |

---

## 4. 初期実装フロー（推奨順序）

### Phase A: インフラ構築（1〜2日）

```
[ ] Supabase プロジェクト新規作成
[ ] articles テーブル作成（仕様書7章スキーマ）
[ ] Supabase Storage バケット作成（article-images）
[ ] .env 設定（SUPABASE_URL / SERVICE_KEY / NEXTJS_REVALIDATE_SECRET）
[ ] ドメイン取得（devicebrief.com 等）
[ ] Vercel プロジェクト作成・Next.js 16 初期設定
```

### Phase B: パイプライン本番稼働（3〜5日）

```
[ ] collect.py 本番テスト（18ソース全確認）
[ ] generate.py 単体テスト（A/B/C型各1本生成・品質確認）
[ ] audit.py 通過率確認（PASS率80%以上を目標に閾値調整）
[ ] publish.py → Supabase INSERT テスト
[ ] GitHub Actions ワークフロー設定（Cron 3回/日）
[ ] 初回バッチ実行 → 記事10〜20本で動作確認
```

### Phase C: フロントエンド実装（1週間）

```
[ ] 記事一覧ページ（カテゴリフィルター・ページネーション）
[ ] 記事詳細ページ（ISR・NewsArticle構造化データ・OGP）
[ ] Progressive Article の「最終更新」バッジ表示
[ ] カテゴリ別RSSフィード（/feed/[category].xml）
[ ] サイトマップ自動生成（/sitemap.xml）
[ ] Aboutページ・編集方針ページ（E-E-A-T対策）
```

### Phase D: SEO・Discovery施策（並行）

```
[ ] Google Search Console 登録・サイトマップ送信
[ ] Google News Publisher Center 申請（記事50本以上が目安）
[ ] NewsArticle + FAQPage 構造化データの動作確認
[ ] Core Web Vitals 計測・LCP 2.5秒以内に調整
[ ] 内部リンク自動生成（同カテゴリ関連記事）
```

### Phase E: 収益化（記事1,000本・月10万PV到達後）

```
[ ] Google AdSense 申請
[ ] Amazonアフィリエイト（製品紹介記事に自動挿入）
[ ] 週次ニュースレター設定（beehiiv or Resend）
[ ] X自動投稿ボット（記事公開時にタイトル+URLをポスト）
```

---

## 5. 現在の設計完了状況

| コンポーネント | ファイル | ステータス |
|---|---|---|
| 収集設計 | `collect_design.py` | 設計完了 |
| 生成設計 | `generate_design.py` | 設計完了（v4: Progressive対応） |
| 監査設計 | `audit.py` | 設計完了 |
| 画像取得設計 | `fetch_image.py` | 設計完了 |
| 公開設計 | `publish_design.py` | 設計完了（v2: Progressive PATCH + Sitemap ping） |
| 仕様書 | `devicebrief_concept.md` | 常時最新 |
| サンプル記事 | `sample_articles.md` + `.docx` | v3完成（3記事） |

### 未実装（次フェーズ）

| 項目 | 優先度 |
|---|---|
| Next.js フロントエンド実装 | 高 |
| Supabase テーブル作成・初期設定 | 高 |
| GitHub Actions ワークフロー | 高 |
| 常駐速報プロセス（VPS/Railway） | 中 |
| スペックDBテーブル設計 | 中 |
| X自動投稿ボット | 低 |

---

## 6. KPI（初期フェーズ）

| 指標 | 1ヶ月目標 | 3ヶ月目標 |
|---|---|---|
| 累計記事数 | 1,000本 | 4,000本 |
| 月間PV | 5,000 | 100,000 |
| Discovery流入比率 | 30% | 40% |
| AdSense申請 | — | 達成 |
| Google News登録 | 申請 | 承認 |

---

## 7. リスクと対策

| リスク | 対策 |
|---|---|
| Claude API コスト超過 | 月¥4,000以内で設計済み。超過時はA型のmax_tokensを削減 |
| Supabase無料枠超過 | Phase 2以降、Proプランへ移行（月$25）。収益化後はペイできる水準 |
| Googleペナルティ（AIコンテンツ） | 編集方針・Aboutページ整備・ハルシネーション絶対禁止・E-E-A-T強化 |
| ソースサイトのフェッチブロック | 4段階フェッチ戦略で対応済み。ブロック時はJina/Playwright切り替え |
| Discovery流入の変動 | ソースの多様化（Google News・X・RSS・メルマガ）でアルゴリズム依存を分散 |
