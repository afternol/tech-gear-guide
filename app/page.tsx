import Image from 'next/image'
import { formatDistanceToNow } from 'date-fns'
import { ja } from 'date-fns/locale'
import { getArticles, getMustCatchArticles, getLatestByCategories } from '@/lib/articles'
import { ArticleCard } from '@/components/ArticleCard'
import { CATEGORY_LABELS } from '@/lib/types'
import type { Category } from '@/lib/types'

export const revalidate = 3600

export default async function HomePage() {
  const [mustCatch, latest, byCategory] = await Promise.all([
    getMustCatchArticles(3),
    getArticles({ limit: 12 }),
    getLatestByCategories(4),
  ])

  return (
    <>
      {/* ── Breaking News Ticker ─────────────────────────────── */}
      {mustCatch.length > 0 && (
        <div className="-mx-4 sm:-mx-6 lg:-mx-8 mb-8 bg-slate-800 flex items-center overflow-hidden h-10 select-none">
          <span className="shrink-0 bg-blue-600 text-white text-xs font-bold px-4 h-full flex items-center uppercase tracking-widest">
            速報
          </span>
          <div className="flex-1 overflow-hidden">
            <div className="flex animate-ticker">
              {[...mustCatch, ...mustCatch, ...mustCatch, ...mustCatch].map((article, i) => (
                <a
                  key={i}
                  href={`/articles/${article.slug}`}
                  className="text-white text-xs whitespace-nowrap px-10 hover:underline shrink-0"
                >
                  ▶ {article.title}
                </a>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Hero: MUST_CATCH ─────────────────────────────────── */}
      {mustCatch.length > 0 && (
        <section className="mb-10">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            <h2 className="text-xs font-bold text-blue-600 uppercase tracking-widest">注目ニュース</h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* 大フィーチャードカード */}
            {mustCatch[0] && (
              <a
                href={`/articles/${mustCatch[0].slug}`}
                className="lg:col-span-2 group relative block rounded-2xl overflow-hidden h-60 sm:h-72 lg:h-[330px] bg-slate-900"
              >
                {mustCatch[0].featured_image_url ? (
                  <Image
                    src={mustCatch[0].featured_image_url}
                    alt={mustCatch[0].title}
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-500 opacity-75"
                    sizes="(max-width: 1024px) 100vw, 66vw"
                    priority
                  />
                ) : (
                  <div className="absolute inset-0 bg-gradient-to-br from-blue-700 to-slate-900" />
                )}
                {/* グラデーションオーバーレイ */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent" />
                {/* テキスト */}
                <div className="absolute inset-0 flex flex-col justify-end p-5 sm:p-6">
                  <span className="text-xs font-bold text-blue-300 uppercase tracking-wider mb-2">
                    {CATEGORY_LABELS[mustCatch[0].category]}
                  </span>
                  <h2 className="text-white font-bold text-xl sm:text-2xl leading-snug line-clamp-3 group-hover:text-blue-100 transition-colors">
                    {mustCatch[0].title}
                  </h2>
                  <p className="text-gray-400 text-xs mt-3">
                    {formatDistanceToNow(new Date(mustCatch[0].published_at), { addSuffix: true, locale: ja })}
                  </p>
                </div>
                <span className="absolute top-4 left-4 text-xs font-bold px-2.5 py-1 rounded-full bg-blue-600 text-white shadow">
                  注目
                </span>
              </a>
            )}

            {/* サイドカード（2・3位） */}
            {mustCatch.length > 1 && (
              <div className="flex flex-row lg:flex-col gap-4">
                {mustCatch.slice(1).map(article => (
                  <ArticleCard key={article.slug} article={article} />
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* ── 2カラムレイアウト ──────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* メインフィード */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-5">
            <span className="w-1 h-5 bg-blue-600 rounded-full" />
            <h2 className="text-xs font-bold text-gray-900 uppercase tracking-widest">最新記事</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {latest.map(article => (
              <ArticleCard key={article.slug} article={article} />
            ))}
          </div>
          <div className="mt-8 text-center">
            <a
              href="/articles"
              className="inline-block px-8 py-2.5 border border-gray-300 rounded-full text-sm text-gray-600 hover:border-blue-500 hover:text-blue-600 transition-colors"
            >
              もっと見る
            </a>
          </div>
        </div>

        {/* サイドバー: カテゴリ別 */}
        <aside>
          <div className="flex items-center gap-2 mb-5">
            <span className="w-1 h-5 bg-gray-400 rounded-full" />
            <h2 className="text-xs font-bold text-gray-900 uppercase tracking-widest">カテゴリ別</h2>
          </div>
          <div className="space-y-6">
            {(Object.entries(byCategory) as [Category, typeof byCategory[Category]][])
              .filter(([, articles]) => articles.length > 0)
              .map(([category, articles]) => (
                <div key={category} className="border-b border-gray-100 pb-6 last:border-0">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                      {CATEGORY_LABELS[category]}
                    </h3>
                    <a href={`/category/${category}`} className="text-xs text-blue-600 hover:underline">
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
          </div>
        </aside>
      </div>
    </>
  )
}
