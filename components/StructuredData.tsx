import type { Article } from '@/lib/types'

// ── FAQ抽出（## よくある質問 セクションをパース）──────────

function extractFaq(body: string): { question: string; answer: string }[] {
  const section = body.match(/## よくある質問([\s\S]*?)(?=\n## |\n---|\n\*\*出典|$)/)?.[1] ?? ''
  const items: { question: string; answer: string }[] = []
  const blocks = section.split(/\n(?=\*\*Q\.)/).filter(Boolean)

  for (const block of blocks) {
    const q = block.match(/\*\*Q\. (.+?)\*\*/)?.[1]
    const a = block.replace(/\*\*Q\. .+?\*\*/, '').trim()
    if (q && a) items.push({ question: q, answer: a })
  }
  return items
}

// ── NewsArticle 構造化データ ──────────────────────────────

interface Props {
  article: Article
  siteUrl: string
}

export function NewsArticleStructuredData({ article, siteUrl }: Props) {
  const articleUrl = `${siteUrl}/articles/${article.slug}`
  const faqItems   = extractFaq(article.body)

  const newsArticle = {
    '@context':      'https://schema.org',
    '@type':         'NewsArticle',
    headline:        article.title,
    description:     article.seo_description,
    url:             articleUrl,
    datePublished:   article.published_at,
    dateModified:    article.last_major_update_at ?? article.published_at,
    author: {
      '@type': 'Organization',
      name:    'Tech Gear Guide編集部',
      url:     siteUrl,
    },
    publisher: {
      '@type': 'Organization',
      name:    'Tech Gear Guide',
      url:     siteUrl,
      logo: {
        '@type': 'ImageObject',
        url:     `${siteUrl}/logo.png`,
      },
    },
    image: article.featured_image_url
      ? {
          '@type': 'ImageObject',
          url:     article.featured_image_url,
          width:   1200,
          height:  628,
        }
      : undefined,
    keywords: article.tags.join(', '),
    articleSection: article.category,
    inLanguage:     'ja',
  }

  const faqPage = faqItems.length > 0
    ? {
        '@context':  'https://schema.org',
        '@type':     'FAQPage',
        mainEntity:  faqItems.map(({ question, answer }) => ({
          '@type':        'Question',
          name:           question,
          acceptedAnswer: { '@type': 'Answer', text: answer },
        })),
      }
    : null

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(newsArticle) }}
      />
      {faqPage && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqPage) }}
        />
      )}
    </>
  )
}

// ── BreadcrumbList ──────────────────────────────────────────

interface BreadcrumbProps {
  items: { name: string; url: string }[]
}

export function BreadcrumbStructuredData({ items }: BreadcrumbProps) {
  const data = {
    '@context':        'https://schema.org',
    '@type':           'BreadcrumbList',
    itemListElement:   items.map((item, i) => ({
      '@type':   'ListItem',
      position:  i + 1,
      name:      item.name,
      item:      item.url,
    })),
  }
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  )
}
