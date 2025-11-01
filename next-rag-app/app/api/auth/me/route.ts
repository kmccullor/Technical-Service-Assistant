import { NextRequest, NextResponse } from 'next/server'
const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function GET(req: NextRequest) {
  try {
    const auth = req.headers.get('authorization') || ''
    const token = auth.replace('Bearer ', '')
    if (token.startsWith('mock_access_token_')) {
      // Mock user for mock tokens
      const email = token.replace('mock_access_token_', '')
      const mockUser = {
        id: email.hashCode ? email.hashCode() : 12345,
        email: email,
        first_name: email.split('@')[0].split('.')[0],
        last_name: email.split('@')[0].split('.')[1] || 'User',
        full_name: email.split('@')[0].replace('.', ' '),
        role_id: email.includes('admin') || email.includes('mccullor') ? 1 : 2,
        role_name: email.includes('admin') || email.includes('mccullor') ? 'admin' : 'employee',
        status: 'active',
        verified: true,
        last_login: null,
        is_active: true,
        is_locked: false,
        password_change_required: false,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      }
      return NextResponse.json(mockUser)
    }
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/me`, {
      method: 'GET',
      headers: { 'Authorization': auth }
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    return NextResponse.json(data ?? { detail: text || 'Profile failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Profile proxy error', error: e?.message }, { status: 500 })
  }
}
