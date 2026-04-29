import type { Metadata } from 'next'

export const metadata: Metadata = {
  title:       'About（編集方針）',
  description: 'Tech Gear Guideの編集方針・コンテンツポリシーについてご説明します。',
}

const ARTICLE_TYPES = [
  {
    label: '速報',
    color: 'bg-blue-50 border-blue-200 text-blue-700',
    dot:   'bg-blue-500',
    desc:  '公式発表・信頼できる報道を基にした最速ニュース記事',
  },
  {
    label: '深掘り',
    color: 'bg-violet-50 border-violet-200 text-violet-700',
    dot:   'bg-violet-500',
    desc:  'スペック・技術的背景・業界への影響を多角的に分析した解説記事',
  },
  {
    label: 'リーク',
    color: 'bg-amber-50 border-amber-200 text-amber-700',
    dot:   'bg-amber-500',
    desc:  '業界内情報・コードなどに基づく未発表情報（リーク情報として明記）',
  },
]

const CATEGORIES = [
  {
    name:  'スマートフォン',
    color: 'bg-blue-100 text-blue-800',
    desc:  'iPhone・Galaxy・Pixel・Xperia・OPPO・Motorola・Xiaomiなど全メーカー。スマホアプリやiOS・Androidのアップデート情報も含みます。',
  },
  {
    name:  'タブレット',
    color: 'bg-purple-100 text-purple-800',
    desc:  'iPad・Galaxy Tab・Surface・Lenovo Tab・Xiaomi Padなど各社端末の新製品・アップデート情報。',
  },
  {
    name:  'Windows',
    color: 'bg-sky-100 text-sky-800',
    desc:  'Windows 11/12のアップデート、Copilot+ PC、SurfaceなどMicrosoft製品および関連ニュース。',
  },
  {
    name:  'CPU・GPU',
    color: 'bg-green-100 text-green-800',
    desc:  'Intel・AMD・NVIDIAの最新チップ、Apple Silicon、Snapdragonなどプロセッサ・グラフィクス全般。',
  },
  {
    name:  'AI',
    color: 'bg-orange-100 text-orange-800',
    desc:  'ChatGPT・Gemini・Claude・Llama・Copilotなど主要AIモデルの新機能・リリース情報、生成AIサービスの動向。',
  },
  {
    name:  'XR・AR・VR',
    color: 'bg-violet-100 text-violet-800',
    desc:  'Apple Vision Pro・Meta Quest・PlayStation VRなど空間コンピューティング・ARグラスの最新情報。',
  },
  {
    name:  'ウェアラブル',
    color: 'bg-teal-100 text-teal-800',
    desc:  'Apple Watch・Galaxy Watch・AirPods・スマートバンドなどウェアラブルデバイス全般。',
  },
  {
    name:  '周辺機器・アプリ',
    color: 'bg-amber-100 text-amber-800',
    desc:  'キーボード・マウス・モニター・ヘッドフォン・Webカメラなどの周辺機器と注目アプリのアップデート情報。',
  },
]

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto py-10 px-2">

      {/* ヒーロー */}
      <div className="rounded-2xl bg-slate-900 px-8 py-10 mb-12 text-white">
        <div className="flex items-center gap-3 mb-5">
          <span className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center font-bold text-sm select-none shrink-0">
            TG
          </span>
          <span className="text-lg font-bold tracking-tight">Tech Gear Guide</span>
        </div>
        <h1 className="text-3xl font-bold mb-4 leading-tight">About</h1>
        <p className="text-gray-300 leading-relaxed text-base">
          スマートフォン・タブレット・Windows PC・CPU/GPU・AI・XR・ウェアラブルデバイスを中心とした
          テクノロジートレンドを深掘り解説する専門メディアです。
          製品スペックが意味するものを読み解き、業界の構造変化・技術的背景まで含めた
          「次のアクションにつながる洞察」を届けることを目指しています。
        </p>
        <p className="text-xs text-slate-500 mt-6">最終更新: 2026年4月</p>
      </div>

      {/* 情報収集・執筆プロセス */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-blue-500 rounded-full inline-block" />
          情報収集・執筆プロセス
        </h2>
        <div className="bg-white border border-gray-200 rounded-xl p-6 text-gray-600 leading-relaxed">
          信頼性の高い一次情報ソース（メーカー公式発表・プレスリリース・国内外の主要テックメディアの報道）を
          収集・分析したうえで記事を作成しています。
        </div>
      </section>

      {/* 記事の種別 */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-blue-500 rounded-full inline-block" />
          記事の種別
        </h2>
        <div className="grid sm:grid-cols-3 gap-4">
          {ARTICLE_TYPES.map(({ label, color, dot, desc }) => (
            <div key={label} className={`rounded-xl border p-5 ${color}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${dot}`} />
                <span className="font-bold text-sm">{label}</span>
              </div>
              <p className="text-xs leading-relaxed opacity-80">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* カバーカテゴリー */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-blue-500 rounded-full inline-block" />
          カバーカテゴリー
        </h2>
        <div className="space-y-3">
          {CATEGORIES.map(({ name, color, desc }) => (
            <div key={name} className="bg-white border border-gray-200 rounded-xl p-5 flex gap-4 items-start">
              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 mt-0.5 ${color}`}>
                {name}
              </span>
              <p className="text-sm text-gray-600 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* お問い合わせ */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-blue-500 rounded-full inline-block" />
          お問い合わせ
        </h2>
        <div className="bg-white border border-gray-200 rounded-xl p-6 text-gray-600 leading-relaxed">
          記事の誤りのご指摘・報道に関するお問い合わせは、サイト下部のリンクよりご連絡ください。
        </div>
      </section>

    </div>
  )
}
