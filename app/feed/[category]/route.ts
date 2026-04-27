import { NextRequest, NextResponse } from 'next/server'
import { getArticles } from '@/lib/articles'
import { CATEGORY_LABELS } from '@/lib/types'
import type { Category } from '@/lib/types'

const SITE_URL  = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://techgear-guide.com'
const SITE_NAME = 'Tech Gear Guide'

const VALID_CATEGORIES: (Category | 'all')[] = [
  'all', 'smartphone', 'tablet', 'windows', 'cpu_gpu', 'ai', 'general'
]

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ category: string }> }
) {
  const { category: rawParam } = await params
  // URLパラメータから拡張子を除去: "smartphone.xml" → "smartphone"
  const rawCategory = rawParam.replace(/\.xml$/, '')
  const isAll       = rawCategory === 'all'
  const category    = isAll ? undefined : rawCategory as Category

  if (!VALID_CATEGORIES.includes(rawCategory as Category | 'all')) {
    return new NextResponse('Not Found', { status: 404 })
  }

  const articles = await getArticles({ category, limit: 30 })
  const feedTitle = isAll
    ? `${SITE_NAME} 全記事フィード`
    : `${SITE_NAME} - ${CATEGORY_LABELS[category!]}`

  const items = articles.map(a => `
    <item>
      <title><![CDATA[${a.title}]]></title>
      <link>${SITE_URL}/articles/${a.slug}</link>
      <guid isPermaLink="true">${SITE_URL}/articles/${a.slug}</guid>
      <pubDate>${new Date(a.published_at).toUTCString()}</pubDate>
      <description><![CDATA[${a.seo_description}]]></description>
      ${a.featured_image_url
        ? `<enclosure url="${a.featured_image_url}" type="image/jpeg" />`
        : ''}
      ${a.tags.map(t => `<category><![CDATA[${t}]]></category>`).join('')}
    </item>`).join('')

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${feedTitle}</title>
    <link>${SITE_URL}</link>
    <description>スマートフォン・GPU・Windows・AIの最新テックニュースを日本語で</description>
    <language>ja</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${SITE_URL}/feed/${rawCategory}.xml" rel="self" type="application/rss+xml" />
    ${items}
  </channel>
</rss>`

  return new NextResponse(xml, {
    headers: {
      'Content-Type':  'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=1800, stale-while-revalidate=3600',
    },
  })
}
