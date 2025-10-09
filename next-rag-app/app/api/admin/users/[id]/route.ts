import { NextRequest, NextResponse } from 'next/server'
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const auth = req.headers.get('authorization') || ''
    const body = await req.json().catch(() => ({}))
    const r = await fetch(`${RERANKER_BASE_URL}/api/admin/users/${params.id}`, {
      method: 'PATCH',
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
    
    return NextResponse.json(data ?? { detail: text || 'Update user failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Update user proxy error', error: e?.message }, { status: 500 })
  }
}

export async function DELETE(req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const auth = req.headers.get('authorization') || ''
    const r = await fetch(`${RERANKER_BASE_URL}/api/admin/users/${params.id}`, {
      method: 'DELETE',
      headers: { 'Authorization': auth }
    })
    if (r.status === 204) {
      return new NextResponse(null, { status: 204 })
    }
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    return NextResponse.json(data ?? { detail: text || 'Delete user failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Delete user proxy error', error: e?.message }, { status: 500 })
  }
}