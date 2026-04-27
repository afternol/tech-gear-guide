# DeviceBrief サンプル記事集

> 生成日: 2026-04-25（v3: ですます調・見出し柔軟化・アイキャッチ画像方針反映）

---

## 記事1: A型速報 / CPU・GPU / VideoCardz

---META---
title: AMD EXPO 1.2が登場——MRDIMMに正式対応、CUDIMMはZen 6で完全実装へ
slug: amd-expo-1-2-mrdimm-cudimm-zen-6
category: cpu_gpu
tags: [AMD, EXPO, MRDIMM, CUDIMM, DDR5]
article_type: A型速報
seo_description: AMDが新メモリ規格「EXPO 1.2」を発表。MRDIMMの正式サポートと部分的なCUDIMM対応を追加。フルCUDIMMサポートは次世代アーキテクチャZen 6での実装が予定されています。
featured_image_source: press
featured_image_credit: AMD Newsroom
---END_META---

AMDのメモリオーバークロック規格「EXPO」が1.2へアップデートされました。著名なメモリ最適化ツール開発者「1usmus」が詳細を公開しており、MRDIMM（Multiplexed Rank DIMM）への正式対応と、部分的なCUDIMM（Compression UDIMM）サポートの追加が主な変更点です。

## EXPO 1.2で広がったメモリ規格の対応範囲

今回のアップデートで、AMDプラットフォームが対応するDDR5メモリ規格が大きく拡充されました。

| 規格 | EXPO 1.0/1.1 | EXPO 1.2 |
|---|---|---|
| 標準DDR5 UDIMM | ✅ 対応 | ✅ 対応 |
| MRDIMM | ❌ 非対応 | ✅ 正式対応 |
| CUDIMM | ❌ 非対応 | ⚠️ 部分対応 |

MRDIMMはメモリモジュールに複数のランクを多重化する規格で、AIワークロードやデータセンター用途で需要が急拡大しています。AMプラットフォームでの正式対応は、こうした高負荷環境を想定したシステム構築の選択肢を広げます。

CUDIMMへの対応は今回の1.2では「部分的」にとどまります。1usmusによると、フルサポートはAMDの次世代アーキテクチャ「Zen 6」での実装が予定されているとのことです。

## IntelのXMPと何が違うのか

EXPOはDDR5向けのAMD独自オーバークロック規格で、IntelのXMP（Extreme Memory Profile）に対応するものです。最新のDDR5メモリは多くの場合、両規格のプロファイルを内蔵しています。

Intelは同時期にXMP側でもCUDIMMやLPCUDIMMへの対応拡充を進めており、今回のEXPO 1.2はそれに対応する形での更新となります。両社ともに次世代メモリ規格のエコシステム整備を急いでいる状況です。

## Zen 6とCUDIMMのロードマップ

完全なCUDIMMサポートが予定されているZen 6は、2026年後半から2027年の投入が見込まれます。CUDIMMはホスト側のコンピュート機能をメモリモジュール上に移すことで、高いオーバークロック耐性と電力効率の両立を目指す規格です。

今回EXPO 1.2で部分対応を先行提供することで、メモリメーカーがCUDIMMプロファイルの検証・最適化を進めやすくなります。Zen 6リリースに向けてエコシステム全体を段階的に整備する布石と捉えることができます。

AM5プラットフォームをお使いの方は、各マザーボードメーカーのBIOSアップデートを通じてEXPO 1.2が順次利用可能になる見込みです。

---

**出典**
- [AMD EXPO 1.2 now available, adds partial CUDIMM support and three new Chinese memory vendors](https://videocardz.com/newz/amd-expo-1-2-now-available-adds-partial-cudimm-support-and-three-new-chinese-memory-vendors) — VideoCardz

---

---

## 記事2: C型リーク / スマートフォン / 9to5Mac

---META---
title: 【リーク】iPhone 17 Pro Maxは前世代より厚い——ダミーユニット比較でiPhone Ultraとの設計差も明確に
slug: iphone-17-pro-max-thicker-dummy-unit-iphone-ultra
category: smartphone
tags: [iPhone 17, iPhone 17 Pro Max, iPhone Ultra, Apple, ダミーユニット, リーク]
article_type: C型リーク
source_reliability: 4
seo_description: 9to5Macが入手したダミーユニット画像から、iPhone 17 Pro Maxが前モデルより厚くなっていることが判明。同時に公開されたiPhone Ultraのダミーユニットとの比較でも設計方針の違いが明らかになっています。
featured_image_source: press
featured_image_credit: Apple Newsroom
---END_META---

> **情報の確度: ★★★★☆**（出所: 9to5Mac）

9to5Macが入手したダミーユニット（量産前の外形確認用モックアップ）の比較画像から、2026年秋発売見込みの「iPhone 17 Pro Max」が前世代より厚みが増していることが確認されました。あわせて公開されたiPhone Ultraのダミーユニットとの比較では、両機種の設計方向性の違いも浮き彫りになっています。

## ダミーユニットで確認された変更点

今回判明した情報と確認状況を整理します。

| 確認項目 | 内容 | 確認状況 |
|---|---|---|
| 厚さ | 前世代より増加（数mm程度） | ダミーユニットで確認 |
| 幅・高さ | 変化あり（詳細未確認） | 未確認 |
| iPhone Ultra比較 | Ultraの方が明らかに大型 | ダミーユニットで確認 |
| 素材・仕上げ | 不明 | ダミーユニットでは判定不可 |

厚さが増加している理由として有力視されているのはバッテリー容量の拡大です。現行モデルでのバッテリー持ちへの不満は根強く、Appleが薄さよりも実用性を優先した設計変更に踏み切った可能性があります。

## 9to5Macの情報精度をどう評価するか

9to5Macは過去に多数の正確なiPhone関連リークを報じており、Appleサプライチェーンに関する情報の精度は業界でも高く評価されているメディアです。確度を★★★★☆とした根拠は以下の通りです。

- 情報源がダミーユニット（外形精度が高い）である点
- 9to5Macの過去のiPhone関連リーク的中率の高さ
- ただし最終設計変更の可能性がゼロではない点

ダミーユニットは量産前にサプライヤーへ配布される外形確認用のモックアップで、最終製品の寸法をほぼ正確に反映していることが多い情報源です。過去のiPhoneシリーズでも概ね一致しています。

## iPhone Ultra vs Pro Max——ラインナップ戦略の変化

今回初めてラインナップへの追加が見込まれるiPhone Ultraのダミーユニットとの比較では、Pro Maxとは明確に異なるサイズ感が確認されています。UltraはPro Maxよりさらに大型・厚い設計で、Apple Watch Ultraと同様のコンセプト——耐久性・バッテリー・カメラを極限まで高めたモデル——が想定されています。

Pro MaxとUltraを並立させることで、Appleはより広い価格帯をカバーする戦略へ転換する可能性があります。現行のPro Maxは国内実勢価格で18〜20万円台に位置しており、Ultraはそれを上回る価格帯になるとみられています。

---

**出典**
- [iPhone 18 Pro Max may be thicker, iPhone Ultra dummy unit compared to 17 Pro Max](https://9to5mac.com/2026/04/23/iphone-18-pro-max-may-be-thicker-iphone-ultra-dummy-unit-compared-to-17-pro-max/) — 9to5Mac

---

---

## 記事3: A型速報 / AI / Neowin

---META---
title: OpenAI、ChatGPTに「Workspace Agents」追加——チームでAIエージェントを構築・共有する新機能
slug: openai-chatgpt-workspace-agents-enterprise
category: ai
tags: [OpenAI, ChatGPT, AIエージェント, Workspace Agents, 企業向けAI]
article_type: A型速報
seo_description: OpenAIがChatGPTに「Workspace Agents」を追加。組織内でAIエージェントを設計・共有できる新機能で、Microsoft Copilot AgentsやGoogle Agentspaceと直接競合します。現在リサーチプレビュー段階です。
featured_image_source: press
featured_image_credit: OpenAI News
---END_META---

OpenAIが「Workspace Agents」と呼ぶ新機能をChatGPTへ追加しました。チームや企業がAIエージェントを独自に設計・構築して組織内のメンバーと共有できる仕組みで、現在はリサーチプレビューとして提供されています。

## Workspace Agentsの主な機能

Workspace AgentsはChatGPTのインターフェイス上で動作し、組織固有のワークフローに合わせたエージェントを構築・管理できます。

- 複数のエージェントを作成してチーム内で共有・再利用できる
- 外部ツールとの連携や複数ステップにわたる自律的なタスクを実行できる
- 社内ナレッジをエージェントに読み込ませた業務支援が可能
- 従来のカスタム指示より高度な設定が可能

単純な質問応答を超えた業務プロセスの自動化を想定した設計で、OpenAIは「自律的なワークスペースエージェント」と位置づけています。

## Microsoft・Googleとの比較

企業向けAIエージェント市場では各社が急速に機能を整備しており、今回の発表はその競争に直接参入するものです。

MicrosoftはMicrosoft 365 CopilotにAgents機能を統合しており、SharePoint・Teams・OutlookといったM365製品との親和性を強みとしています。GoogleはAgentspaceでGoogle WorkspaceとGeminiの統合を推進しており、GmailやGoogleドキュメントとの連携が中心です。

OpenAIのWorkspace Agentsが差別化できる点として、既存のChatGPT Team/Enterpriseプランからシームレスに移行できることが挙げられます。追加のツール導入なしに機能を拡張できるため、すでにChatGPTを業務利用している組織にとっては導入の敷居が低くなっています。

## リサーチプレビューの現状と注意点

現時点ではリサーチプレビューのため、利用可能な機能範囲・正式価格・全プランへの対応状況は確定していません。OpenAIはフィードバックをもとに機能を拡充したうえで正式版へ移行する予定としています。

エンタープライズ向けにはデータが学習に使用されないことが保証されていますが、社内機密情報をエージェントに処理させる際は、自社のセキュリティポリシーとの整合性を事前に確認することが推奨されます。

---

**出典**
- [OpenAI launches autonomous Workspace Agents in ChatGPT](https://www.neowin.net/news/openai-launches-autonomous-workspace-agents-in-chatgpt/) — Neowin

---
