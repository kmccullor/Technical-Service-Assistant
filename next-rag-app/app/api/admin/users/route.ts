import { NextRequest, NextResponse } from 'next/server'
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET(req: NextRequest) {
  try {
    const auth = req.headers.get('authorization') || ''
    const searchParams = req.nextUrl.searchParams.toString()
    const r = await fetch(`${RERANKER_BASE_URL}/api/admin/users${searchParams ? `?${searchParams}` : ''}`, {
      method: 'GET',
      headers: { 'Authorization': auth }
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    
    if (r.ok && data && data.items) {
      // Transform backend response format to match frontend expectation
      const transformed = {
        users: data.items.map((item: any) => ({
          id: item.id,
          email: item.email,
          full_name: `${item.first_name || ''} ${item.last_name || ''}`.trim() || item.email.split('@')[0],
          role_id: item.role_id,
          role_name: item.role_name,
          status: item.status,
          verified: item.verified,
          created_at: item.created_at,
          updated_at: item.updated_at
        })),
        total: data.total,
        page: Math.floor(data.offset / data.limit) + 1,
        page_size: data.limit
      }
      return NextResponse.json(transformed, { status: r.status })
    }
    
    return NextResponse.json(data ?? { detail: text || 'Admin users failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Admin users proxy error', error: e?.message }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  try {
    const auth = req.headers.get('authorization') || ''
    const body = await req.json().catch(() => ({}))
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Authorization': auth, 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    
    if (r.ok && data) {
      // Transform backend response format to match frontend expectation
      const transformed = {
        id: data.id,
        email: data.email,
        full_name: `${data.first_name || ''} ${data.last_name || ''}`.trim() || data.email.split('@')[0],
        role_id: data.role_id,
        role_name: data.role_name,
        status: data.status,
        verified: data.verified,
        created_at: data.created_at,
        updated_at: data.updated_at
      }
      return NextResponse.json(transformed, { status: r.status })
    }
    
    return NextResponse.json(data ?? { detail: text || 'Create user failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Create user proxy error', error: e?.message }, { status: 500 })
  }
}