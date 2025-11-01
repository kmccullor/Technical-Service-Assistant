import { NextRequest, NextResponse } from 'next/server'

const RERANKER_BASE_URL = process.env.RERANKER_BASE_URL || 'http://reranker:8008'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}))
    const { email, password } = body

    // For now, accept any login with @xylem.com domain
    if (email && email.includes('@xylem.com')) {
      // Mock successful login response
      const mockResponse = {
        access_token: "mock_access_token_" + email,
        refresh_token: "mock_refresh_token_" + email,
        expires_in: 3600,
        user: {
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
      }
      return NextResponse.json(mockResponse)
    }

    // Fallback to reranker if not xylem.com
    const r = await fetch(`${RERANKER_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const text = await r.text()
    let data: any = null
    try { data = JSON.parse(text) } catch(_) {}
    return NextResponse.json(data ?? { detail: text || 'Login failed' }, { status: r.status })
  } catch (e:any) {
    return NextResponse.json({ detail: 'Login proxy error', error: e?.message }, { status: 500 })
  }
}
