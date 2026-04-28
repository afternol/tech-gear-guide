'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { Element, Text } from 'hast'
import { EmbedCard } from '@/components/EmbedCard'

function resolveEmbed(node: Element): string | null {
  if (node.children.length !== 1) return null
  const child = node.children[0]
  if (child.type !== 'element') return null
  const el = child as Element
  if (el.tagName !== 'a') return null
  const href = el.properties?.href as string | undefined
  if (!href || !/^https?:\/\//.test(href)) return null
  const text = el.children
    .filter((c): c is Text => c.type === 'text')
    .map(c => c.value)
    .join('')
  return text === href ? href : null
}

const components: Components = {
  h2: ({ children }) => (
    <h2 className="text-2xl font-bold text-gray-900 mt-10 mb-4 pb-2 border-b-2 border-gray-200">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-bold text-gray-800 mt-7 mb-2">{children}</h3>
  ),
  p: ({ children, node }) => {
    if (node) {
      const embedUrl = resolveEmbed(node as Element)
      if (embedUrl) return <EmbedCard url={embedUrl} />
    }
    return <p className="text-gray-700 leading-relaxed my-4 text-[15px]">{children}</p>
  },
  ul: ({ children }) => (
    <ul className="my-4 ml-5 space-y-1.5 list-disc text-gray-700">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-4 ml-5 space-y-1.5 list-decimal text-gray-700">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed text-[15px]">{children}</li>
  ),
  table: ({ children }) => (
    <div className="my-6 overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
      <table className="min-w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-gray-50 border-b border-gray-200">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="px-4 py-3 text-left font-bold text-gray-700 text-xs uppercase tracking-wider whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-3 text-gray-700 border-t border-gray-100">{children}</td>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-6 pl-5 border-l-4 border-blue-500 bg-blue-50 py-3 pr-4 rounded-r-xl text-gray-700 not-italic">
      {children}
    </blockquote>
  ),
  strong: ({ children }) => (
    <strong className="font-bold text-gray-900">{children}</strong>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 hover:text-blue-800 underline underline-offset-2 decoration-blue-300"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-8 border-gray-200" />,
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
