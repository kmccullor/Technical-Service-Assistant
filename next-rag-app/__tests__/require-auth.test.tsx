import React from 'react'
import { render, screen, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import { RequireAuth } from '@/src/components/auth/RequireAuth'
import { AuthProvider, useAuth } from '@/src/context/AuthContext'

// Helper component to expose auth state for test when user provided
function MockContent() {
  const { user } = useAuth()
  return <div>Protected {user?.email}</div>
}

describe.skip('RequireAuth', () => {
  beforeEach(() => {
    delete (globalThis as any)._tsaFetchWrapped
    const store: Record<string,string> = {}
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: (k: string) => store[k] || null,
        setItem: (k: string, v: string) => { store[k] = v },
        removeItem: (k: string) => { delete store[k] },
        clear: () => { Object.keys(store).forEach(k => delete store[k]) }
      },
      configurable: true
    })
  })

  it('renders redirect placeholder when unauthenticated', async () => {
    global.fetch = jest.fn(async () => new Response('{}', { status: 200 })) as any
    await act(async () => {
      render(<AuthProvider><RequireAuth><MockContent /></RequireAuth></AuthProvider>)
    })
    expect(screen.getByText(/redirecting to login/i)).toBeInTheDocument()
  })

  it('shows protected content when authenticated', async () => {
    global.fetch = jest.fn(async (input) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/auth/me')) {
        return new Response(JSON.stringify({
          id: 1,
          email: 'admin@example.com',
          first_name: 'Admin',
          last_name: 'User',
          full_name: 'Admin User',
          role_id: 1,
          role_name: 'admin',
          status: 'active',
          verified: true
        }), { status: 200 })
      }
      return new Response('{}', { status: 200 })
    }) as any
    window.localStorage.setItem('tsa_auth_v1', JSON.stringify({ accessToken: 'X', refreshToken: 'R', expiresAt: Date.now()+60000 }))
    await act(async () => {
      render(<AuthProvider><RequireAuth><MockContent /></RequireAuth></AuthProvider>)
    })
    // allow effect
    await act(async () => { await new Promise(r => setTimeout(r, 5)) })
    expect(screen.getByText(/protected admin@example.com/i)).toBeInTheDocument()
  })
})
