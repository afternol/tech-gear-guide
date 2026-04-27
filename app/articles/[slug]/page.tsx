import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import Image from 'next/image'
import { format } from 'date-fns'
import { ja } from 'date-fns/locale'

import { getArticleBySlug, getRelatedArticles, getAllSlugs } from '@/lib/articles'
import { ArticleBody } from '@/components/ArticleBody'
import { ArticleCard } from '@/components/ArticleCard'
import { NewsArticleStructuredData, BreadcrumbStructuredData } from '@/components/StructuredData'
import { CATEGORY_LABELS, CATEGORY_COLORS, ARTICLE_TYPE_LABELS } from '@/lib/types'

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://devicebrief.com'

// 記事詳細ページは5分キャッシュ（publish.pyのISRで即時更新）
export const revalidate = 300

// ビルド時に上位記事を静的生成（残りはオンデマンドISR）
export async function generateStaticParams() {
  try {
    const slugs = await getAllSlugs()
    return slugs.slice(0, 200).map(({ slug }) => ({ slug }))
  } catch {
    return []  // Supabase未設定時はオンデマンドISRにフォールバック
  }
}

// ── OGP / メタデータ ────────────────────────────────────────

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params
  const article  = await getArticleBySlug(slug)
  if (!article) return {}

  const url    = `${SITE_URL}/articles/${article.slug}`
  const ogImage = article.featured_image_url || `${SITE_URL}/og-default.jpg`

  return {
    title:       article.title,
    description: article.seo_description,
    alternates:  { canonical: url },
    openGraph: {
      type:        'article',
      url,
      title:       article.title,
      description: article.seo_description,
      publishedTime: article.published_at,
      modifiedTime:  article.last_major_update_at ?? article.published_at,
      tags:          article.tags,
      images: [{ url: ogImage, width: 1200, height: 628, alt: article.title }],
    },
    twitter: {
      card:        'summary_large_image',
      title:       article.title,
      description: article.seo_description,
      images:      [ogImage],
    },
  }
}

// ── ページ本体 ───────────────────────────────────────────────

export default async function ArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const article  = await getArticleBySlug(slug)
  if (!article) notFound()

  const related = await getRelatedArticles(article)

  const publishedDate = format(new Date(article.published_at), 'yyyy年M月d日', { locale: ja })
  const updatedDate   = article.last_major_update_at
    ? format(new Date(article.last_major_update_at), 'yyyy年M月d日 HH:mm', { locale: ja })
    : null
  const isProgressive = article.progressive_phase !== null

  return (
    <>
      {/* 構造化データ */}
      <NewsArticleStructuredData article={article} siteUrl={SITE_URL} />
      <BreadcrumbStructuredData
        items={[
          { name: 'ホーム',                         url: SITE_URL },
          { name: CATEGORY_LABELS[article.category], url: `${SITE_URL}/category/${article.category}` },
          { name: article.title,                    url: `${SITE_URL}/articles/${article.slug}` },
        ]}
      />

      <div className="max-w-3xl mx-auto">
        {/* パンくず */}
        <nav className="text-xs text-gray-500 mb-4 flex items-center gap-1">
          <a href="/" className="hover:text-gray-700">ホーム</a>
          <span>/</span>
          <a href={`/category/${article.category}`} className="hover:text-gray-700">
            {CATEGORY_LABELS[article.category]}
          </a>
          <span>/</span>
          <span className="text-gray-400 truncate max-w-xs">{article.title}</span>
        </nav>

        {/* ヘッダー */}
        <header className="mb-6">
          {/* バッジ群 */}
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${CATEGORY_COLORS[article.category]}`}>
              {CATEGORY_LABELS[article.category]}
            </span>
            {article.article_type !== 'A型速報' && (
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-700">
                {ARTICLE_TYPE_LABELS[article.article_type]}
              </span>
            )}
            {article.is_must_catch && (
              <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-red-500 text-white">
                注目
              </span>
            )}
          </div>

          {/* タイトル */}
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 leading-tight mb-4">
            {article.title}
          </h1>

          {/* C型: 確度表示 */}
          {article.article_type === 'C型リーク' && article.source_reliability > 0 && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm">
              <span className="font-semibold text-amber-800">情報の確度: </span>
              <span className="text-amber-700">
                {'★'.repeat(article.source_reliability)}{'☆'.repeat(5 - article.source_reliability)}
              </span>
              <span className="ml-1 text-amber-600 text-xs">（{article.source_reliability}/5）</span>
            </div>
          )}

          {/* メタ情報 */}
          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
            <time dateTime={article.published_at}>{publishedDate} 公開</time>
            {updatedDate && (
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                <span className="text-green-700 font-medium">最終更新: {updatedDate}</span>
              </span>
            )}
            {isProgressive && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                Phase {article.progressive_phase} / 3
              </span>
            )}
            <span>DeviceBrief編集部</span>
          </div>
        </header>

        {/* アイキャッチ画像 */}
        {article.featured_image_url && (
          <div className="relative aspect-[16/9] mb-8 rounded-xl overflow-hidden bg-gray-100">
            <Image
              src={article.featured_image_url}
              alt={article.title}
              fill
              className="object-cover"
              priority
              sizes="(max-width: 768px) 100vw, 768px"
            />
            {article.featured_image_credit && (
              <p className="absolute bottom-2 right-2 text-xs text-white/70 bg-black/40 px-2 py-0.5 rounded">
                {article.featured_image_credit}
              </p>
            )}
          </div>
        )}

        {/* 本文 */}
        <article className="prose-custom">
          <ArticleBody body={article.body} />
        </article>

        {/* タグ */}
        {article.tags.length > 0 && (
          <div className="mt-8 pt-6 border-t border-gray-200">
            <div className="flex flex-wrap gap-2">
              {article.tags.map(tag => (
                <span
                  key={tag}
                  className="text-xs px-3 py-1 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200 cursor-default"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 免責事項 */}
        <p className="mt-6 text-xs text-gray-400 leading-relaxed">
          本記事はAI支援により作成されています。情報の正確性には最大限注意していますが、
          最終確認は各メーカー・公式サイトでお願いします。
        </p>
      </div>

      {/* 関連記事 */}
      {related.length > 0 && (
        <section className="max-w-5xl mx-auto mt-12">
          <h2 className="text-base font-bold text-gray-900 mb-4">関連記事</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {related.map(a => (
              <ArticleCard key={a.slug} article={a} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
