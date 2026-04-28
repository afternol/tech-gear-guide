import type { Metadata, Viewport } from 'next'
import { Noto_Sans_JP } from 'next/font/google'
import './globals.css'
import { MobileNav } from '@/components/MobileNav'

const notoSansJP = Noto_Sans_JP({
  subsets:  ['latin'],
  weight:   ['400', '500', '700'],
  display:  'swap',
  variable: '--font-noto-sans-jp',
})

const SITE_URL  = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://techgear-guide.com'
const SITE_NAME = 'Tech Gear Guide'
const SITE_DESC = 'スマホ・PC・GPU・AI・XR・ウェアラブルの最新テックニュースを日本語で。海外権威メディアの情報を専門家視点で解説。'

export const metadata: Metadata = {
  metadataBase:  new URL(SITE_URL),
  title:         { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description:   SITE_DESC,
  openGraph: {
    type:        'website',
    locale:      'ja_JP',
    url:         SITE_URL,
    siteName:    SITE_NAME,
    title:       SITE_NAME,
    description: SITE_DESC,
    images: [{ url: '/og-default.jpg', width: 1200, height: 628 }],
  },
  twitter: {
    card:        'summary_large_image',
    site:        '@techgearguide_jp',
    title:       SITE_NAME,
    description: SITE_DESC,
  },
  robots: {
    index:  true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large' },
  },
  alternates: {
    types: {
      'application/rss+xml': [
        { url: '/feed/all.xml',        title: `${SITE_NAME} 全記事フィード` },
        { url: '/feed/smartphone.xml', title: `${SITE_NAME} スマートフォン` },
        { url: '/feed/ai.xml',         title: `${SITE_NAME} AI` },
        { url: '/feed/xr.xml',         title: `${SITE_NAME} XR・AR・VR` },
        { url: '/feed/wearable.xml',   title: `${SITE_NAME} ウェアラブル` },
      ],
    },
  },
}

export const viewport: Viewport = {
  width:        'device-width',
  initialScale: 1,
  themeColor:   '#0f172a',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" className={notoSansJP.variable}>
      <body className="min-h-screen bg-gray-50 font-sans antialiased">
        <Header />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  )
}

const NAV_ITEMS = [
  { label: 'スマホ',       href: '/category/smartphone' },
  { label: 'タブレット',   href: '/category/tablet' },
  { label: 'Windows',      href: '/category/windows' },
  { label: 'CPU・GPU',     href: '/category/cpu_gpu' },
  { label: 'AI',           href: '/category/ai' },
  { label: 'XR・AR・VR',  href: '/category/xr' },
  { label: 'ウェアラブル', href: '/category/wearable' },
]

function Header() {
  return (
    <header className="bg-slate-900 sticky top-0 z-50 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between relative">
        {/* ロゴ */}
        <a href="/" className="flex items-center gap-2.5 shrink-0">
          <span className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold text-xs select-none">
            TG
          </span>
          <span className="text-base font-bold text-white tracking-tight hidden sm:block">
            Tech Gear Guide
          </span>
          <span className="text-base font-bold text-white tracking-tight sm:hidden">
            TGG
          </span>
        </a>

        {/* デスクトップナビ */}
        <nav className="hidden lg:flex items-center gap-6 text-sm">
          {NAV_ITEMS.map(({ label, href }) => (
            <a
              key={href}
              href={href}
              className="text-gray-300 hover:text-white whitespace-nowrap transition-colors duration-150 py-1"
            >
              {label}
            </a>
          ))}
        </nav>

        {/* モバイルハンバーガー */}
        <MobileNav />
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="mt-20 bg-slate-900 text-gray-400">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-10">
          {/* ブランド */}
          <div className="col-span-2 md:col-span-1">
            <a href="/" className="flex items-center gap-2.5 mb-4">
              <span className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold text-xs select-none">
                TG
              </span>
              <span className="text-white font-bold text-sm">Tech Gear Guide</span>
            </a>
            <p className="text-xs text-gray-500 leading-relaxed">
              海外テックメディア20社以上を常時モニタリング。スマホ・PC・AI・XRの最新情報を正確にお届けします。
            </p>
          </div>

          {/* カテゴリ 前半 */}
          <div>
            <h4 className="text-white font-semibold mb-4 text-xs uppercase tracking-wider">カテゴリ</h4>
            <ul className="space-y-2.5">
              {NAV_ITEMS.slice(0, 4).map(({ label, href }) => (
                <li key={href}>
                  <a href={href} className="text-xs hover:text-white transition-colors">{label}</a>
                </li>
              ))}
            </ul>
          </div>

          {/* カテゴリ 後半 */}
          <div>
            <h4 className="invisible text-xs mb-4">-</h4>
            <ul className="space-y-2.5">
              {NAV_ITEMS.slice(4).map(({ label, href }) => (
                <li key={href}>
                  <a href={href} className="text-xs hover:text-white transition-colors">{label}</a>
                </li>
              ))}
            </ul>
          </div>

          {/* サイト情報 */}
          <div>
            <h4 className="text-white font-semibold mb-4 text-xs uppercase tracking-wider">サイト情報</h4>
            <ul className="space-y-2.5">
              <li><a href="/about"        className="text-xs hover:text-white transition-colors">編集方針</a></li>
              <li><a href="/privacy"      className="text-xs hover:text-white transition-colors">プライバシーポリシー</a></li>
              <li><a href="/feed/all.xml" className="text-xs hover:text-white transition-colors">RSSフィード</a></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-slate-800 pt-6 text-center">
          <p className="text-xs text-gray-600">© 2026 Tech Gear Guide. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}
