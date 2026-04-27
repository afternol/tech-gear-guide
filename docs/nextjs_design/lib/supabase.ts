import { createClient } from '@supabase/supabase-js'

const supabaseUrl     = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY!

// Server Component・API Route 用（service_role: RLSバイパス）
export function createServerClient() {
  return createClient(supabaseUrl, supabaseServiceKey, {
    auth: { persistSession: false },
  })
}

// Client Component 用（anon: RLS適用・公開記事のみ読み取り可）
export function createBrowserClient() {
  return createClient(supabaseUrl, supabaseAnonKey)
}
