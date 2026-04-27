// DeviceBrief 型定義

export type Category = 'smartphone' | 'tablet' | 'windows' | 'cpu_gpu' | 'ai' | 'general'
export type ArticleType = 'A型速報' | 'B型深掘り' | 'C型リーク'

export interface ArticleSource {
  title: string
  url:   string
  media: string
}

export interface Article {
  id:                    string
  title:                 string
  slug:                  string
  body:                  string       // Markdown
  category:              Category
  tags:                  string[]
  article_type:          ArticleType
  source_reliability:    number       // 0-5（C型のみ）
  sources:               ArticleSource[]
  featured_image_url:    string
  featured_image_source: string       // press / unsplash / fallback
  featured_image_credit: string
  seo_description:       string
  published_at:          string       // ISO8601
  created_at:            string
  last_major_update_at:  string | null
  progressive_phase:     number | null  // 1/2/3 or null
  is_published:          boolean
  is_must_catch:         boolean
  is_leak:               boolean
}

// 一覧表示用（bodyを除いた軽量版）
export type ArticleSummary = Omit<Article, 'body' | 'sources'>

export const CATEGORY_LABELS: Record<Category, string> = {
  smartphone: 'スマートフォン',
  tablet:     'タブレット',
  windows:    'Windows',
  cpu_gpu:    'CPU・GPU',
  ai:         'AI',
  general:    'その他',
}

export const CATEGORY_COLORS: Record<Category, string> = {
  smartphone: 'bg-blue-100 text-blue-800',
  tablet:     'bg-purple-100 text-purple-800',
  windows:    'bg-sky-100 text-sky-800',
  cpu_gpu:    'bg-green-100 text-green-800',
  ai:         'bg-orange-100 text-orange-800',
  general:    'bg-gray-100 text-gray-700',
}

export const ARTICLE_TYPE_LABELS: Record<ArticleType, string> = {
  'A型速報':  '速報',
  'B型深掘り': '深掘り',
  'C型リーク': 'リーク',
}
