// Tech Gear Guide 型定義

export type Category =
  | 'smartphone'
  | 'tablet'
  | 'windows'
  | 'cpu_gpu'
  | 'ai'
  | 'xr'
  | 'wearable'
  | 'peripheral'
  | 'general'

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
  body:                  string
  category:              Category
  tags:                  string[]
  article_type:          ArticleType
  sources:               ArticleSource[]
  featured_image_url:    string
  featured_image_source: string
  featured_image_credit: string
  seo_description:       string
  published_at:          string
  created_at:            string
  last_major_update_at:  string | null
  progressive_phase:     number | null
  is_published:          boolean
  is_must_catch:         boolean
  is_leak:               boolean
  is_indexed:            boolean
  noindex_reason:        string
}

export type ArticleSummary = Omit<Article, 'body' | 'sources'>

export const CATEGORY_LABELS: Record<Category, string> = {
  smartphone: 'スマートフォン',
  tablet:     'タブレット',
  windows:    'Windows',
  cpu_gpu:    'CPU・GPU',
  ai:         'AI',
  xr:         'XR・AR・VR',
  wearable:   'ウェアラブル',
  peripheral: '周辺機器・アプリ',
  general:    'その他',
}

export const CATEGORY_COLORS: Record<Category, string> = {
  smartphone: 'bg-blue-100 text-blue-800',
  tablet:     'bg-purple-100 text-purple-800',
  windows:    'bg-sky-100 text-sky-800',
  cpu_gpu:    'bg-green-100 text-green-800',
  ai:         'bg-orange-100 text-orange-800',
  xr:         'bg-violet-100 text-violet-800',
  wearable:   'bg-teal-100 text-teal-800',
  peripheral: 'bg-amber-100 text-amber-800',
  general:    'bg-gray-100 text-gray-700',
}

export const ARTICLE_TYPE_LABELS: Record<ArticleType, string> = {
  'A型速報':   '速報',
  'B型深掘り': '深掘り',
  'C型リーク': 'リーク',
}
