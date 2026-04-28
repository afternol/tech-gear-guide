'use client'
import { useState } from 'react'

const NAV_ITEMS = [
  { label: 'スマホ',       href: '/category/smartphone' },
  { label: 'タブレット',   href: '/category/tablet' },
  { label: 'Windows',      href: '/category/windows' },
  { label: 'CPU・GPU',     href: '/category/cpu_gpu' },
  { label: 'AI',           href: '/category/ai' },
  { label: 'XR・AR・VR',  href: '/category/xr' },
  { label: 'ウェアラブル', href: '/category/wearable' },
]

export function MobileNav() {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative lg:hidden">
      <button
        onClick={() => setOpen(o => !o)}
        aria-label={open ? 'メニューを閉じる' : 'メニューを開く'}
        className="p-2 text-gray-400 hover:text-white transition-colors"
      >
        {open ? (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 w-52 bg-slate-800 rounded-xl shadow-2xl border border-slate-700 z-50 py-2 overflow-hidden">
            {NAV_ITEMS.map(({ label, href }) => (
              <a
                key={href}
                href={href}
                className="block px-4 py-3 text-sm text-gray-300 hover:text-white hover:bg-slate-700 transition-colors"
                onClick={() => setOpen(false)}
              >
                {label}
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
