import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { getArticles, getArticleCount } from '@/lib/articles'
import { ArticleCard } from '@/components/ArticleCard'
import { CATEGORY_LABELS } from '@/lib/types'
import type { Category } from '@/lib/types'

export const revalidate = 1800

const VALID_CATEGORIES: Category[] = ['smartphone', 'tablet', 'windows', 'cpu_gpu', 'ai', 'xr', 'wearable', 'general']
const PER_PAGE = 20

const CATEGORY_ICONS: Record<Category, string> = {
  smartphone: '📱',
  tablet:     '🖥️',
  windows:    '🪟',
  cpu_gpu:    '⚡',
  ai:         '🤖',
  xr:         '🥽',
  wearable:   '⌚',
  general:    '📰',
}

const CATEGORY_HERO: Record<Category, string> = {
  smartphone: 'from-blue-600 to-blue-900',
  tablet:     'from-purple-600 to-purple-900',
  windows:    'from-sky-600 to-sky-900',
  cpu_gpu:    'from-green-600 to-green-900',
  ai:         'from-orange-500 to-orange-800',
  xr:         'from-violet-600 to-violet-900',
  wearable:   'from-teal-600 to-teal-900',
  general:    'from-gray-600 to-gray-900',
}

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
    description: `${label}に関する最新テックニュース。専門的な視点で深掘り解説。`,
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
      {/* カテゴリヒーロー */}
      <div className={`-mx-4 sm:-mx-6 lg:-mx-8 mb-8 px-6 sm:px-10 lg:px-14 py-9 bg-gradient-to-r ${CATEGORY_HERO[category]}`}>
        <div className="flex items-center gap-4">
          <span className="text-4xl sm:text-5xl" role="img" aria-label={label}>
            {CATEGORY_ICONS[category]}
          </span>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white">{label}</h1>
            <p className="text-sm text-white/60 mt-1">全{total.toLocaleString()}件の記事</p>
          </div>
        </div>
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
        <nav className="mt-10 flex justify-center items-center gap-3">
          {page > 1 ? (
            <a
              href={`/category/${category}?page=${page - 1}`}
              className="px-5 py-2 border border-gray-300 rounded-full text-sm hover:border-blue-500 hover:text-blue-600 transition-colors"
            >
              ← 前へ
            </a>
          ) : (
            <span className="px-5 py-2 rounded-full text-sm text-gray-300 cursor-default select-none">← 前へ</span>
          )}
          <span className="text-sm text-gray-500 min-w-[4rem] text-center">
            {page} <span className="text-gray-300">/</span> {totalPages}
          </span>
          {page < totalPages ? (
            <a
              href={`/category/${category}?page=${page + 1}`}
              className="px-5 py-2 border border-gray-300 rounded-full text-sm hover:border-blue-500 hover:text-blue-600 transition-colors"
            >
              次へ →
            </a>
          ) : (
            <span className="px-5 py-2 rounded-full text-sm text-gray-300 cursor-default select-none">次へ →</span>
          )}
        </nav>
      )}
    </>
  )
}
