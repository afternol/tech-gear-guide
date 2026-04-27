import type { Metadata, Viewport } from 'next'
import { Noto_Sans_JP } from 'next/font/google'
import './globals.css'

const notoSansJP = Noto_Sans_JP({
  subsets:  ['latin'],
  weight:   ['400', '500', '700'],
  display:  'swap',
  variable: '--font-noto-sans-jp',
})

const SITE_URL  = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://devicebrief.com'
const SITE_NAME = 'DeviceBrief'
const SITE_DESC = 'スマートフォン・GPU・Windows・AIの最新テックニュースを日本語で。海外権威メディアの情報を専門家視点で解説。'

export const metadata: Metadata = {
  metadataBase:  new URL(SITE_URL),
  title:         { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description:   SITE_DESC,
  openGraph: {
    type:       'website',
    locale:     'ja_JP',
    url:        SITE_URL,
    siteName:   SITE_NAME,
    title:      SITE_NAME,
    description: SITE_DESC,
    images: [{ url: '/og-default.jpg', width: 1200, height: 628 }],
  },
  twitter: {
    card:        'summary_large_image',
    site:        '@devicebrief_jp',
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

function Header() {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <a href="/" className="text-xl font-bold text-blue-700 tracking-tight">
          DeviceBrief
        </a>
        <nav className="hidden md:flex items-center gap-5 text-sm text-gray-600">
          {[
            { label: 'スマホ',  href: '/category/smartphone' },
            { label: 'タブレット', href: '/category/tablet' },
            { label: 'Windows', href: '/category/windows' },
            { label: 'CPU・GPU', href: '/category/cpu_gpu' },
            { label: 'AI',      href: '/category/ai' },
          ].map(({ label, href }) => (
            <a key={href} href={href} className="hover:text-blue-700 transition-colors">
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
      <div className="max-w-7xl mx-auto px-4 py-8 text-sm text-gray-500 flex flex-col md:flex-row justify-between gap-4">
        <p>© 2026 DeviceBrief（Reinforz Insight）</p>
        <div className="flex gap-4">
          <a href="/about"          className="hover:text-gray-700">編集方針</a>
          <a href="/privacy"        className="hover:text-gray-700">プライバシーポリシー</a>
          <a href="/feed/all.xml"   className="hover:text-gray-700">RSSフィード</a>
        </div>
      </div>
    </footer>
  )
}
