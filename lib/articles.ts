import { createServerClient } from './supabase'
import type { Article, ArticleSummary, Category } from './types'

const SUMMARY_COLUMNS = [
  'id', 'title', 'slug', 'category', 'tags',
  'article_type', 'source_reliability',
  'featured_image_url', 'featured_image_credit',
  'seo_description', 'published_at', 'last_major_update_at',
  'progressive_phase', 'is_must_catch', 'is_leak',
].join(',')

// ─── 記事一覧 ──────────────────────────────────────────────

export async function getArticles(options: {
  category?: Category
  limit?:    number
  offset?:   number
} = {}): Promise<ArticleSummary[]> {
  const { category, limit = 20, offset = 0 } = options
  const db = createServerClient()

  let query = db
    .from('articles')
    .select(SUMMARY_COLUMNS)
    .eq('is_published', true)
    .order('published_at', { ascending: false })
    .range(offset, offset + limit - 1)

  if (category) query = query.eq('category', category)

  const { data, error } = await query
  if (error) return []
  return (data ?? []) as unknown as ArticleSummary[]
}

// ─── 記事詳細 ──────────────────────────────────────────────

export async function getArticleBySlug(slug: string): Promise<Article | null> {
  const { data, error } = await createServerClient()
    .from('articles')
    .select('*')
    .eq('slug', slug)
    .eq('is_published', true)
    .single()

  if (error) return null
  return data as unknown as Article
}

// ─── MUST_CATCH速報（トップページヒーロー用）──────────────

export async function getMustCatchArticles(limit = 5): Promise<ArticleSummary[]> {
  const { data, error } = await createServerClient()
    .from('articles')
    .select(SUMMARY_COLUMNS)
    .eq('is_published', true)
    .eq('is_must_catch', true)
    .order('published_at', { ascending: false })
    .limit(limit)

  if (error) return []
  return (data ?? []) as unknown as ArticleSummary[]
}

// ─── カテゴリ別最新記事（トップページサイドバー用）────────

export async function getLatestByCategories(limitPerCategory = 4): Promise<
  Record<Category, ArticleSummary[]>
> {
  const categories: Category[] = ['smartphone', 'tablet', 'windows', 'cpu_gpu', 'ai', 'xr', 'wearable', 'general']
  const db = createServerClient()

  const results = await Promise.all(
    categories.map(cat =>
      db
        .from('articles')
        .select(SUMMARY_COLUMNS)
        .eq('is_published', true)
        .eq('category', cat)
        .order('published_at', { ascending: false })
        .limit(limitPerCategory)
    )
  )

  return Object.fromEntries(
    categories.map((cat, i) => [cat, (results[i].data ?? []) as unknown as ArticleSummary[]])
  ) as Record<Category, ArticleSummary[]>
}

// ─── 関連記事（同カテゴリ・同タグ優先）──────────────────

export async function getRelatedArticles(
  article: Pick<Article, 'slug' | 'category' | 'tags'>,
  limit = 4,
): Promise<ArticleSummary[]> {
  const { data } = await createServerClient()
    .from('articles')
    .select(SUMMARY_COLUMNS)
    .eq('is_published', true)
    .eq('category', article.category)
    .neq('slug', article.slug)
    .order('published_at', { ascending: false })
    .limit(limit)

  return (data ?? []) as unknown as ArticleSummary[]
}

// ─── サイトマップ用スラッグ一覧 ──────────────────────────

export async function getAllSlugs(): Promise<{ slug: string; published_at: string }[]> {
  const { data, error } = await createServerClient()
    .from('articles')
    .select('slug, published_at')
    .eq('is_published', true)
    .order('published_at', { ascending: false })

  if (error) return []
  return data ?? []
}

// ─── 総記事数（ページネーション用）──────────────────────

export async function getArticleCount(category?: Category): Promise<number> {
  let query = createServerClient()
    .from('articles')
    .select('id', { count: 'exact', head: true })
    .eq('is_published', true)

  if (category) query = query.eq('category', category)
  const { count } = await query
  return count ?? 0
}
