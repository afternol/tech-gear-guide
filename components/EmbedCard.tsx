'use client'

import { useEffect, useRef } from 'react'

// ── URL判別 ─────────────────────────────────────────────────

function getYouTubeId(url: string): string | null {
  const m =
    url.match(/youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/) ||
    url.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/) ||
    url.match(/youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/)
  return m ? m[1] : null
}

function isTweetUrl(url: string): boolean {
  return /(?:twitter\.com|x\.com)\/\w+\/status\/\d+/.test(url)
}

// ── YouTube埋め込み ─────────────────────────────────────────

function YouTubeEmbed({ videoId }: { videoId: string }) {
  return (
    <div className="my-6 aspect-video w-full overflow-hidden rounded-xl bg-gray-100">
      <iframe
        src={`https://www.youtube.com/embed/${videoId}?rel=0`}
        title="YouTube動画"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        className="h-full w-full"
        loading="lazy"
      />
    </div>
  )
}

// ── Twitter / X 埋め込み ────────────────────────────────────

function TwitterEmbed({ tweetUrl }: { tweetUrl: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const win = window as Window & { twttr?: { widgets: { load: (el?: HTMLElement | null) => void } } }
    const load = () => win.twttr?.widgets.load(ref.current)

    if (win.twttr?.widgets) {
      load()
      return
    }
    if (!document.getElementById('twitter-wjs')) {
      const s    = document.createElement('script')
      s.id       = 'twitter-wjs'
      s.src      = 'https://platform.twitter.com/widgets.js'
      s.async    = true
      s.onload   = load
      document.body.appendChild(s)
    }
  }, [tweetUrl])

  return (
    <div ref={ref} className="my-6 flex justify-center [&_.twitter-tweet]:mx-auto">
      <blockquote className="twitter-tweet" data-lang="ja" data-dnt="true">
        <a href={tweetUrl} />
      </blockquote>
    </div>
  )
}

// ── 汎用リンクカード ────────────────────────────────────────

function LinkCard({ url }: { url: string }) {
  let hostname = url
  try { hostname = new URL(url).hostname.replace(/^www\./, '') } catch { /* noop */ }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="my-4 flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm hover:bg-gray-100 transition-colors no-underline"
    >
      <svg className="h-4 w-4 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
      </svg>
      <span className="flex-1 truncate font-medium text-blue-700">{url}</span>
      <span className="shrink-0 text-xs text-gray-400">{hostname} ↗</span>
    </a>
  )
}

// ── メインディスパッチ ─────────────────────────────────────

interface Props { url: string }

export function EmbedCard({ url }: Props) {
  const ytId = getYouTubeId(url)
  if (ytId) return <YouTubeEmbed videoId={ytId} />
  if (isTweetUrl(url)) return <TwitterEmbed tweetUrl={url} />
  return <LinkCard url={url} />
}
