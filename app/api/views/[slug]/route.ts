import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@/lib/supabase'

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params
  const sb = createServerClient()
  await sb.from('page_views').insert({ slug })
  return NextResponse.json({ ok: true })
}
