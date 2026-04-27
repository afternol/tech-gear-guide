import Link from 'next/link'
import Image from 'next/image'
import type { ArticleSummary } from '@/lib/types'
import { CATEGORY_LABELS, CATEGORY_COLORS, ARTICLE_TYPE_LABELS } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { ja } from 'date-fns/locale'

interface Props {
  article: ArticleSummary
  size?: 'default' | 'large'
}

export function ArticleCard({ article, size = 'default' }: Props) {
  const timeAgo = formatDistanceToNow(new Date(article.published_at), {
    addSuffix: true,
    locale: ja,
  })
  const isUpdated = article.last_major_update_at !== null

  return (
    <Link
      href={`/articles/${article.slug}`}
      className="group block rounded-xl overflow-hidden border border-gray-100 hover:border-gray-300 hover:shadow-md transition-all bg-white"
    >
      {/* サムネイル */}
      <div className={`relative overflow-hidden bg-gray-100 ${size === 'large' ? 'aspect-[16/7]' : 'aspect-[16/9]'}`}>
        {article.featured_image_url ? (
          <Image
            src={article.featured_image_url}
            alt={article.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center">
            <span className="text-gray-400 text-sm">{CATEGORY_LABELS[article.category]}</span>
          </div>
        )}

        {/* バッジ群（左上） */}
        <div className="absolute top-2 left-2 flex gap-1.5">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${CATEGORY_COLORS[article.category]}`}>
            {CATEGORY_LABELS[article.category]}
          </span>
          {article.article_type !== 'A型速報' && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-white/90 text-gray-600">
              {ARTICLE_TYPE_LABELS[article.article_type]}
            </span>
          )}
        </div>

        {/* MUST_CATCH ラベル（右上） */}
        {article.is_must_catch && (
          <span className="absolute top-2 right-2 text-xs font-bold px-2 py-0.5 rounded-full bg-red-500 text-white">
            注目
          </span>
        )}

        {/* Progressive 更新バッジ */}
        {isUpdated && (
          <span className="absolute bottom-2 right-2 text-xs px-2 py-0.5 rounded-full bg-black/60 text-white">
            更新あり
          </span>
        )}
      </div>

      {/* テキスト */}
      <div className="p-3">
        <h3 className={`font-semibold text-gray-900 leading-snug group-hover:text-blue-700 transition-colors line-clamp-3 ${size === 'large' ? 'text-base' : 'text-sm'}`}>
          {article.title}
        </h3>
        <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
          <span>{timeAgo}</span>
          {article.is_leak && (
            <span className="text-amber-600 font-medium">
              {'★'.repeat(article.source_reliability)}{'☆'.repeat(5 - article.source_reliability)}
            </span>
          )}
        </div>
        {article.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {article.tags.slice(0, 3).map(tag => (
              <span key={tag} className="text-xs text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  )
}
