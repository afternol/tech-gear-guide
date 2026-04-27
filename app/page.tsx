import { getArticles, getMustCatchArticles, getLatestByCategories } from '@/lib/articles'
import { ArticleCard } from '@/components/ArticleCard'
import { CATEGORY_LABELS } from '@/lib/types'
import type { Category } from '@/lib/types'

// トップページは1時間キャッシュ（ISR）
export const revalidate = 3600

export default async function HomePage() {
  const [mustCatch, latest, byCategory] = await Promise.all([
    getMustCatchArticles(3),
    getArticles({ limit: 12 }),
    getLatestByCategories(4),
  ])

  return (
    <>
      {/* ── ヒーロー: MUST_CATCH速報 ──────────────────────── */}
      {mustCatch.length > 0 && (
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-1.5 h-5 bg-red-500 rounded-full" />
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide">注目ニュース</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {mustCatch.map(article => (
              <ArticleCard key={article.slug} article={article} size="large" />
            ))}
          </div>
        </section>
      )}

      {/* ── 2カラムレイアウト ──────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* メインフィード */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-1.5 h-5 bg-blue-600 rounded-full" />
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide">最新記事</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {latest.map(article => (
              <ArticleCard key={article.slug} article={article} />
            ))}
          </div>
          <div className="mt-6 text-center">
            <a
              href="/articles"
              className="inline-block px-6 py-2 border border-gray-300 rounded-full text-sm text-gray-600 hover:border-gray-500 hover:text-gray-900 transition-colors"
            >
              もっと見る
            </a>
          </div>
        </div>

        {/* サイドバー: カテゴリ別最新 */}
        <aside className="space-y-8">
          {(Object.entries(byCategory) as [Category, typeof byCategory[Category]][])
            .filter(([, articles]) => articles.length > 0)
            .map(([category, articles]) => (
              <div key={category}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-gray-900">
                    {CATEGORY_LABELS[category]}
                  </h3>
                  <a
                    href={`/category/${category}`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    一覧 →
                  </a>
                </div>
                <div className="space-y-3">
                  {articles.slice(0, 3).map(article => (
                    <a
                      key={article.slug}
                      href={`/articles/${article.slug}`}
                      className="block text-sm text-gray-700 hover:text-blue-700 leading-snug line-clamp-2 transition-colors"
                    >
                      {article.title}
                    </a>
                  ))}
                </div>
              </div>
            ))
          }
        </aside>
      </div>
    </>
  )
}
