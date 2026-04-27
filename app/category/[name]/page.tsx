import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { getArticles, getArticleCount } from '@/lib/articles'
import { ArticleCard } from '@/components/ArticleCard'
import { CATEGORY_LABELS } from '@/lib/types'
import type { Category } from '@/lib/types'

export const revalidate = 1800

const VALID_CATEGORIES: Category[] = ['smartphone', 'tablet', 'windows', 'cpu_gpu', 'ai', 'xr', 'wearable', 'general']
const PER_PAGE = 20

export function generateStaticParams() {
  return VALID_CATEGORIES.map(name => ({ name }))
}

export async function generateMetadata(
  { params }: { params: Promise<{ name: string }> }
): Promise<Metadata> {
  const { name } = await params
  const category = name as Category
  if (!VALID_CATEGORIES.includes(category)) return {}
  const label = CATEGORY_LABELS[category]
  return {
    title:       `${label}の最新ニュース`,
    description: `${label}に関する最新テックニュース。海外権威メディアの情報を日本語で解説。`,
  }
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params:       Promise<{ name: string }>
  searchParams: Promise<{ page?: string }>
}) {
  const { name }   = await params
  const sp         = await searchParams
  const category   = name as Category
  if (!VALID_CATEGORIES.includes(category)) notFound()

  const page   = Math.max(1, Number(sp.page ?? 1))
  const offset = (page - 1) * PER_PAGE

  const [articles, total] = await Promise.all([
    getArticles({ category, limit: PER_PAGE, offset }),
    getArticleCount(category),
  ])

  const totalPages = Math.ceil(total / PER_PAGE)
  const label      = CATEGORY_LABELS[category]

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{label}</h1>
        <p className="text-sm text-gray-500 mt-1">全{total.toLocaleString()}件</p>
      </div>

      {articles.length === 0 ? (
        <p className="text-gray-500">記事がありません。</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {articles.map(article => (
            <ArticleCard key={article.slug} article={article} />
          ))}
        </div>
      )}

      {/* ページネーション */}
      {totalPages > 1 && (
        <nav className="mt-8 flex justify-center gap-2">
          {page > 1 && (
            <a
              href={`/category/${category}?page=${page - 1}`}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            >
              ← 前へ
            </a>
          )}
          <span className="px-4 py-2 text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          {page < totalPages && (
            <a
              href={`/category/${category}?page=${page + 1}`}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            >
              次へ →
            </a>
          )}
        </nav>
      )}
    </>
  )
}
