'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { Element, Text } from 'hast'
import { EmbedCard } from '@/components/EmbedCard'

// 段落がベアURL1つだけで構成されているか判定してEmbedCardに委譲
function resolveEmbed(node: Element): string | null {
  if (node.children.length !== 1) return null
  const child = node.children[0]
  if (child.type !== 'element') return null
  const el = child as Element
  if (el.tagName !== 'a') return null
  const href = el.properties?.href as string | undefined
  if (!href || !/^https?:\/\//.test(href)) return null
  // テキストがURLそのものかチェック（bare autolink）
  const text = el.children
    .filter((c): c is Text => c.type === 'text')
    .map(c => c.value)
    .join('')
  return text === href ? href : null
}

const components: Components = {
  h2: ({ children }) => (
    <h2 className="text-xl font-bold text-gray-900 mt-8 mb-3 pb-2 border-b border-gray-200">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-semibold text-gray-800 mt-6 mb-2">{children}</h3>
  ),
  p: ({ children, node }) => {
    if (node) {
      const embedUrl = resolveEmbed(node as Element)
      if (embedUrl) return <EmbedCard url={embedUrl} />
    }
    return <p className="text-gray-700 leading-relaxed my-3">{children}</p>
  },
  ul: ({ children }) => (
    <ul className="my-3 ml-4 space-y-1 list-disc text-gray-700">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-3 ml-4 space-y-1 list-decimal text-gray-700">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto">
      <table className="min-w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-gray-50">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-semibold text-gray-700 border border-gray-200">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-gray-700 border border-gray-200">{children}</td>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-4 pl-4 border-l-4 border-amber-400 bg-amber-50 py-2 pr-3 rounded-r-lg text-amber-900 font-medium">
      {children}
    </blockquote>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 hover:underline"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-6 border-gray-200" />,
  code: ({ children }) => (
    <code className="bg-gray-100 text-gray-800 text-sm px-1.5 py-0.5 rounded font-mono">
      {children}
    </code>
  ),
}

interface Props {
  body: string
}

export function ArticleBody({ body }: Props) {
  return (
    <div className="article-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {body}
      </ReactMarkdown>
    </div>
  )
}
