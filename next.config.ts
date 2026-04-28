import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: '/:path*',
        has: [{ type: 'host', value: 'devicebrief.vercel.app' }],
        destination: 'https://techgear-guide.com/:path*',
        permanent: true,
      },
    ]
  },
  images: {
    remotePatterns: [
      // Supabase Storage
      { protocol: 'https', hostname: '*.supabase.co', pathname: '/storage/v1/object/public/**' },
      // 公式プレスルーム（fetch_image.pyで取得）
      { protocol: 'https', hostname: 'www.apple.com' },
      { protocol: 'https', hostname: 'news.samsung.com' },
      { protocol: 'https', hostname: 'nvidianews.nvidia.com' },
      { protocol: 'https', hostname: 'www.amd.com' },
      { protocol: 'https', hostname: 'news.microsoft.com' },
      { protocol: 'https', hostname: 'blog.google' },
      { protocol: 'https', hostname: 'openai.com' },
      // Unsplash
      { protocol: 'https', hostname: 'images.unsplash.com' },
    ],
  },
}

export default nextConfig
