import type { Metadata } from 'next'

export const metadata: Metadata = {
  title:       'プライバシーポリシー',
  description: 'Tech Gear Guideのプライバシーポリシーについてご説明します。',
}

export default function PrivacyPage() {
  return (
    <div className="max-w-2xl mx-auto py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">プライバシーポリシー</h1>
      <p className="text-sm text-gray-400 mb-10">最終更新: 2026年4月</p>

      <div className="space-y-10 text-gray-700 leading-relaxed">
        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">基本方針</h2>
          <p>
            Tech Gear Guide（以下「当サイト」）は、ユーザーのプライバシーを尊重し、
            個人情報の保護に関する法律（個人情報保護法）をはじめとする関連法令を遵守します。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">収集する情報</h2>
          <p>当サイトでは、以下の情報を自動的に収集する場合があります。</p>
          <ul className="mt-3 space-y-2 list-disc list-inside">
            <li>アクセスログ（IPアドレス、ブラウザの種類、参照元URL、アクセス日時など）</li>
            <li>Cookieおよびこれに類する技術を用いて収集される閲覧情報</li>
          </ul>
          <p className="mt-3">
            当サイトは会員登録機能を持たず、氏名・メールアドレスなどの個人情報を直接収集することはありません。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">Googleアナリティクスの利用</h2>
          <p>
            当サイトはアクセス解析のためにGoogle アナリティクス（Google LLC）を使用しています。
            Google アナリティクスはCookieを使用してデータを収集します。
            このデータは匿名で収集されており、個人を特定するものではありません。
            この機能はCookieを無効化することで収集を拒否できます。
            詳細はGoogleのプライバシーポリシーをご参照ください。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">ブックマーク機能について</h2>
          <p>
            当サイトのブックマーク機能は、お使いのブラウザのlocalStorageを使用して
            端末内のみにデータを保存します。サーバーへの送信は行いません。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">外部リンクについて</h2>
          <p>
            当サイトには外部サイトへのリンクが含まれます。
            リンク先のサイトのプライバシーポリシーについては、各サイトの規定をご確認ください。
            当サイトはリンク先サイトのコンテンツ・プライバシーポリシーについて責任を負いません。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">免責事項</h2>
          <p>
            当サイトに掲載する情報は、信頼できる一次ソースをもとに作成していますが、
            その正確性・完全性を保証するものではありません。
            当サイトの情報を利用したことにより生じた損害について、当サイトは責任を負いかねます。
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-3">プライバシーポリシーの変更</h2>
          <p>
            当サイトは、必要に応じてプライバシーポリシーを変更することがあります。
            変更後のポリシーは本ページに掲載した時点で効力を生じます。
          </p>
        </section>
      </div>
    </div>
  )
}
