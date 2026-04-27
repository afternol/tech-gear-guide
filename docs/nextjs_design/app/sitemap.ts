import type { MetadataRoute } from 'next'
import { getAllSlugs } from '@/lib/articles'

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://devicebrief.com'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const slugs = await getAllSlugs()

  const articleUrls: MetadataRoute.Sitemap = slugs.map(({ slug, published_at }) => ({
    url:          `${SITE_URL}/articles/${slug}`,
    lastModified: new Date(published_at),
    changeFrequency: 'weekly',
    priority:     0.8,
  }))

  const staticUrls: MetadataRoute.Sitemap = [
    { url: SITE_URL,                              lastModified: new Date(), changeFrequency: 'hourly',  priority: 1.0 },
    { url: `${SITE_URL}/category/smartphone`,     lastModified: new Date(), changeFrequency: 'hourly',  priority: 0.9 },
    { url: `${SITE_URL}/category/ai`,             lastModified: new Date(), changeFrequency: 'hourly',  priority: 0.9 },
    { url: `${SITE_URL}/category/cpu_gpu`,        lastModified: new Date(), changeFrequency: 'daily',   priority: 0.8 },
    { url: `${SITE_URL}/category/windows`,        lastModified: new Date(), changeFrequency: 'daily',   priority: 0.8 },
    { url: `${SITE_URL}/category/tablet`,         lastModified: new Date(), changeFrequency: 'daily',   priority: 0.7 },
    { url: `${SITE_URL}/category/general`,        lastModified: new Date(), changeFrequency: 'daily',   priority: 0.6 },
    { url: `${SITE_URL}/about`,                   lastModified: new Date(), changeFrequency: 'monthly', priority: 0.3 },
  ]

  return [...staticUrls, ...articleUrls]
}
