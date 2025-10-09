import { NextRequest, NextResponse } from 'next/server'
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET(req: NextRequest) {
  try {
    const auth = req.headers.get('authorization') || ''
    const r = await fetch(`${RERANKER_BASE_URL}/api/admin/roles`, {
      method: 'GET',
      headers: { 'Authorization': auth }
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    
    if (r.ok && data && data.items) {
      // Transform backend response format to match frontend expectation
      const transformed = data.items.map((item: any) => ({
        id: item.id,
        name: item.name,
        description: item.description,
        system: item.is_system_role,
        permissions: item.permissions
      }))
      return NextResponse.json(transformed, { status: r.status })
    }
    
    return NextResponse.json(data ?? { detail: text || 'Admin roles failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Admin roles proxy error', error: e?.message }, { status: 500 })
  }
}