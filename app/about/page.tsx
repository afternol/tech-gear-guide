import type { Metadata } from 'next'

export const metadata: Metadata = {
  title:       'About（編集方針）',
  description: 'Tech Gear Guideの編集方針・コンテンツポリシーについてご説明します。',
}

export default function AboutPage() {
  return (
    <div className="max-w-2xl mx-auto py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">About（編集方針）</h1>
      <p className="text-sm text-gray-400 mb-10">最終更新: 2026年4月</p>

      <div className="space-y-10 text-gray-700 leading-relaxed">
        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">Tech Gear Guideについて</h2>
          <p>
            Tech Gear Guideは、スマートフォン・タブレット・Windows PC・CPU/GPU・AI・XR・ウェアラブルデバイスを中心とした
            テクノロジートレンドを深掘り解説する専門メディアです。
            製品スペックの数字が意味するものを読み解き、業界の構造変化や技術的背景まで含めた
            「次のアクションにつながる洞察」を届けることを目指しています。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">情報収集・執筆プロセス</h2>
          <p>
            当メディアは、信頼性の高い一次情報ソース（メーカー公式発表・プレスリリース・国内外の主要テックメディアの報道）を
            収集・分析したうえで記事を作成しています。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">記事の種別</h2>
          <ul className="space-y-3 mb-6">
            <li>
              <span className="font-semibold text-gray-900">速報</span>
              　― 公式発表・信頼できる報道を基にした最速ニュース記事
            </li>
            <li>
              <span className="font-semibold text-gray-900">深掘り</span>
              　― スペック・技術的背景・業界への影響を多角的に分析した解説記事
            </li>
            <li>
              <span className="font-semibold text-gray-900">リーク</span>
              　― 業界内情報・コードなどに基づく未発表情報（リーク情報として明記）
            </li>
          </ul>
          <h3 className="text-base font-bold text-gray-900 mb-3">カバーカテゴリー</h3>
          <ul className="space-y-2.5">
            <li>
              <span className="font-semibold text-gray-900">スマートフォン</span>
              　― iPhone・Galaxy・Pixel・Xperia・OPPO・Motorola・Xiaomiなど、あらゆるメーカー・機種の最新動向。スマホアプリやOS（iOS・Android）のアップデート情報も含みます。
            </li>
            <li>
              <span className="font-semibold text-gray-900">タブレット</span>
              　― iPad・Galaxy Tab・Surface・Lenovo Tab・Xiaomi Padなど、各社タブレット端末の新製品・アップデート情報。
            </li>
            <li>
              <span className="font-semibold text-gray-900">Windows</span>
              　― Windows 11/12のアップデート、CoPilot+ PC、SurfaceなどMicrosoft製品および周辺ニュース。
            </li>
            <li>
              <span className="font-semibold text-gray-900">CPU・GPU</span>
              　― Intel・AMD・NVIDIAの最新チップ、Apple Silicon、Snapdragonなどプロセッサ・グラフィクス全般のベンチマーク・発売情報。
            </li>
            <li>
              <span className="font-semibold text-gray-900">AI</span>
              　― ChatGPT・Gemini・Claude・Llama・Copilotなど主要AIモデルの新機能・リリース情報、生成AIサービスの動向。
            </li>
            <li>
              <span className="font-semibold text-gray-900">XR・AR・VR</span>
              　― Apple Vision Pro・Meta Quest・PlayStation VRなどの空間コンピューティング・ARグラスの最新情報。
            </li>
            <li>
              <span className="font-semibold text-gray-900">ウェアラブル</span>
              　― Apple Watch・Galaxy Watch・AirPods・スマートバンドなどウェアラブルデバイス全般。
            </li>
            <li>
              <span className="font-semibold text-gray-900">周辺機器・アプリ</span>
              　― キーボード・マウス・モニター・ヘッドフォン・Webカメラなどの周辺機器、注目アプリのアップデート情報。
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">お問い合わせ</h2>
          <p>
            記事の誤りのご指摘・報道に関するお問い合わせは、サイト下部のリンクよりご連絡ください。
          </p>
        </section>
      </div>
    </div>
  )
}
