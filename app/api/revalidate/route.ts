import { revalidatePath } from 'next/cache'
import { NextRequest, NextResponse } from 'next/server'

/**
 * ISR revalidate エンドポイント
 * publish.py から呼ばれる: GET /api/revalidate?secret=XXX&path=/articles/slug&category=smartphone
 */
export async function GET(req: NextRequest) {
  const secret   = req.nextUrl.searchParams.get('secret')
  const path     = req.nextUrl.searchParams.get('path')
  const category = req.nextUrl.searchParams.get('category')

  if (secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ message: 'Invalid secret' }, { status: 401 })
  }
  if (!path) {
    return NextResponse.json({ message: 'path is required' }, { status: 400 })
  }

  try {
    revalidatePath(path)
    revalidatePath('/')
    revalidatePath('/articles')
    revalidatePath('/sitemap.xml')

    if (category) {
      revalidatePath(`/category/${category}`)
    } else {
      revalidatePath('/category/[name]', 'page')
    }

    return NextResponse.json({ revalidated: true, path, category })
  } catch (err) {
    return NextResponse.json({ message: 'Revalidation failed', err }, { status: 500 })
  }
}
