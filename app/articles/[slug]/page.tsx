import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import Image from 'next/image'
import { formatJST } from '@/lib/date'
import { getArticleBySlug, getRelatedArticles, getAllSlugs } from '@/lib/articles'
import { ArticleBody } from '@/components/ArticleBody'
import { ArticleCard } from '@/components/ArticleCard'
import { NewsArticleStructuredData, BreadcrumbStructuredData } from '@/components/StructuredData'
import { ReadingProgress } from '@/components/ReadingProgress'
import { ViewTracker } from '@/components/ViewTracker'
import { ShareButtons } from '@/components/ShareButtons'
import { BookmarkButton } from '@/components/BookmarkButton'
import { CATEGORY_LABELS, CATEGORY_COLORS, ARTICLE_TYPE_LABELS } from '@/lib/types'

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? 'https://techgear-guide.com').replace(/^﻿/, '').trim()

export const revalidate = 300

export async function generateStaticParams() {
  try {
    const slugs = await getAllSlugs()
    return slugs.slice(0, 200).map(({ slug }) => ({ slug }))
  } catch {
    return []
  }
}


export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params
  const article  = await getArticleBySlug(slug)
  if (!article) return {}

  const url     = `${SITE_URL}/articles/${article.slug}`
  const ogImage = article.featured_image_url || `${SITE_URL}/og-default.jpg`

  return {
    title:       article.title,
    description: article.seo_description,
    alternates:  { canonical: url },
    robots:      article.is_indexed === false ? 'noindex,follow' : 'index,follow',
    openGraph: {
      type:          'article',
      url,
      title:         article.title,
      description:   article.seo_description,
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

export default async function ArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug }  = await params
  const article   = await getArticleBySlug(slug)
  if (!article) notFound()

  const related    = await getRelatedArticles(article)
  const articleUrl    = `${SITE_URL}/articles/${article.slug}`
  const publishedDate = formatJST(article.published_at, 'yyyy年M月d日')
  const updatedDate   = article.last_major_update_at
    ? formatJST(article.last_major_update_at, 'yyyy年M月d日 HH:mm')
    : null
  const isProgressive = article.progressive_phase !== null

  return (
    <>
      {/* 読書進捗バー */}
      <ReadingProgress />
      {/* PV計測 */}
      <ViewTracker slug={article.slug} />

      {/* 構造化データ */}
      <NewsArticleStructuredData article={article} siteUrl={SITE_URL} />
      <BreadcrumbStructuredData
        items={[
          { name: 'ホーム',                          url: SITE_URL },
          { name: CATEGORY_LABELS[article.category], url: `${SITE_URL}/category/${article.category}` },
          { name: article.title,                     url: articleUrl },
        ]}
      />

      <div className="max-w-3xl mx-auto">
        {/* パンくず */}
        <nav className="text-xs text-gray-400 mb-5 flex items-center gap-1.5 flex-wrap">
          <a href="/" className="hover:text-gray-600 transition-colors">ホーム</a>
          <span className="text-gray-300">/</span>
          <a href={`/category/${article.category}`} className="hover:text-gray-600 transition-colors">
            {CATEGORY_LABELS[article.category]}
          </a>
          <span className="text-gray-300">/</span>
          <span className="text-gray-400 truncate max-w-[200px] sm:max-w-xs">{article.title}</span>
        </nav>

        {/* ヘッダー */}
        <header className="mb-6">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${CATEGORY_COLORS[article.category]}`}>
              {CATEGORY_LABELS[article.category]}
            </span>
            {article.article_type !== 'A型速報' && (
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-700">
                {ARTICLE_TYPE_LABELS[article.article_type]}
              </span>
            )}
            {article.is_must_catch && (
              <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-blue-600 text-white">
                注目
              </span>
            )}
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 leading-tight mb-4">
            {article.title}
          </h1>

          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
            <time dateTime={article.published_at}>{publishedDate} 公開</time>
            {updatedDate && (
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                <span className="text-green-700 font-medium text-xs">更新: {updatedDate}</span>
              </span>
            )}
            {isProgressive && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                Phase {article.progressive_phase} / 3
              </span>
            )}
            <span className="text-gray-400 text-xs">Tech Gear Guide 編集部</span>
          </div>
        </header>

        {/* アイキャッチ画像 */}
        {article.featured_image_url && (
          <div className="relative aspect-[16/9] mb-6 rounded-2xl overflow-hidden bg-gray-100 shadow-sm">
            <Image
              src={article.featured_image_url}
              alt={article.title}
              fill
              className="object-cover"
              priority
              sizes="(max-width: 768px) 100vw, 768px"
            />
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
                <a
                  key={tag}
                  href={`/tag/${encodeURIComponent(tag)}`}
                  className="text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
                >
                  #{tag}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* シェア・ブックマーク */}
        <div className="mt-6 pt-6 border-t border-gray-200 flex flex-wrap items-center gap-3">
          <ShareButtons url={articleUrl} title={article.title} />
          <BookmarkButton slug={article.slug} />
        </div>

        {/* 編集部ボックス */}
        <div className="mt-8 p-4 sm:p-5 bg-slate-50 border border-slate-200 rounded-xl flex items-start gap-4">
          <div className="w-11 h-11 bg-slate-800 rounded-full flex items-center justify-center shrink-0 select-none">
            <span className="text-white font-bold text-xs">TG</span>
          </div>
          <div>
            <p className="font-bold text-gray-900 text-sm">Tech Gear Guide 編集部</p>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              最新テクノロジーの動向を独自の視点で分析・解説しています。製品スペックの深読みから業界構造の読み解きまで、テック選びに役立つ洞察を心がけています。
            </p>
          </div>
        </div>
      </div>

      {/* 関連記事 */}
      {related.length > 0 && (
        <section className="max-w-5xl mx-auto mt-14">
          <div className="flex items-center gap-2 mb-5">
            <span className="w-1 h-5 bg-gray-400 rounded-full" />
            <h2 className="text-xs font-bold text-gray-900 uppercase tracking-widest">関連記事</h2>
          </div>
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
