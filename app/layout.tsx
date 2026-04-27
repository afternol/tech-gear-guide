import type { Metadata, Viewport } from 'next'
import { Noto_Sans_JP } from 'next/font/google'
import './globals.css'

const notoSansJP = Noto_Sans_JP({
  subsets:  ['latin'],
  weight:   ['400', '500', '700'],
  display:  'swap',
  variable: '--font-noto-sans-jp',
})

const SITE_URL  = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://techgearguide.jp'
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
  themeColor:   '#1A56DB',
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
  { label: 'スマホ',        href: '/category/smartphone' },
  { label: 'タブレット',    href: '/category/tablet' },
  { label: 'Windows',       href: '/category/windows' },
  { label: 'CPU・GPU',      href: '/category/cpu_gpu' },
  { label: 'AI',            href: '/category/ai' },
  { label: 'XR・AR・VR',   href: '/category/xr' },
  { label: 'ウェアラブル', href: '/category/wearable' },
]

function Header() {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <a href="/" className="text-xl font-bold text-blue-700 tracking-tight shrink-0">
          Tech Gear Guide
        </a>
        <nav className="hidden lg:flex items-center gap-4 text-sm text-gray-600 overflow-x-auto">
          {NAV_ITEMS.map(({ label, href }) => (
            <a key={href} href={href} className="whitespace-nowrap hover:text-blue-700 transition-colors">
              {label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="mt-16 border-t border-gray-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 py-8 text-sm text-gray-500">
        <div className="flex flex-wrap gap-3 mb-4 text-xs">
          {NAV_ITEMS.map(({ label, href }) => (
            <a key={href} href={href} className="hover:text-gray-700">{label}</a>
          ))}
        </div>
        <div className="flex flex-col md:flex-row justify-between gap-3">
          <p>© 2026 Tech Gear Guide（Reinforz Insight）</p>
          <div className="flex gap-4">
            <a href="/about"        className="hover:text-gray-700">編集方針</a>
            <a href="/privacy"      className="hover:text-gray-700">プライバシーポリシー</a>
            <a href="/feed/all.xml" className="hover:text-gray-700">RSSフィード</a>
          </div>
        </div>
      </div>
    </footer>
  )
}
