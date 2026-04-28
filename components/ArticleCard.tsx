import Link from 'next/link'
import Image from 'next/image'
import type { ArticleSummary } from '@/lib/types'
import { CATEGORY_LABELS } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { ja } from 'date-fns/locale'

interface Props {
  article: ArticleSummary
  size?: 'default' | 'large'
}

export function ArticleCard({ article, size = 'default' }: Props) {
  const timeAgo  = formatDistanceToNow(new Date(article.published_at), { addSuffix: true, locale: ja })
  const isUpdated = article.last_major_update_at !== null

  return (
    <Link
      href={`/articles/${article.slug}`}
      className="group block rounded-xl overflow-hidden border border-gray-100 hover:border-gray-200 hover:shadow-lg transition-all duration-200 bg-white"
    >
      {/* サムネイル */}
      <div className={`relative overflow-hidden bg-gray-100 ${size === 'large' ? 'aspect-[16/7]' : 'aspect-[16/9]'}`}>
        {article.featured_image_url ? (
          <Image
            src={article.featured_image_url}
            alt={article.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          />
        ) : (
          <div className="w-full h-full bg-gray-100" />
        )}

        {/* 注目バッジ */}
        {article.is_must_catch && (
          <span className="absolute top-2 right-2 text-xs font-bold px-2 py-0.5 rounded-full bg-blue-600 text-white shadow-sm">
            注目
          </span>
        )}

        {/* 記事タイプバッジ */}
        {article.article_type === 'C型リーク' && (
          <span className="absolute top-2 left-2 text-xs font-bold px-2 py-0.5 rounded-full bg-amber-400 text-amber-900 shadow-sm">
            リーク
          </span>
        )}
        {article.article_type === 'B型深掘り' && (
          <span className="absolute top-2 left-2 text-xs font-medium px-2 py-0.5 rounded-full bg-white/90 text-gray-700 shadow-sm">
            深掘り
          </span>
        )}

        {/* 更新バッジ */}
        {isUpdated && (
          <span className="absolute bottom-2 right-2 text-xs px-2 py-0.5 rounded-full bg-black/70 text-white backdrop-blur-sm">
            更新あり
          </span>
        )}
      </div>

      {/* テキスト */}
      <div className="p-3">
        <h3 className={`font-semibold text-gray-900 leading-snug group-hover:text-blue-700 transition-colors line-clamp-3 ${size === 'large' ? 'text-[15px]' : 'text-[14px]'}`}>
          {article.title}
        </h3>
        <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
          <time dateTime={article.published_at}>{timeAgo}</time>
        </div>
        {article.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {article.tags.slice(0, 2).map(tag => (
              <span key={tag} className="text-xs text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  )
}
