import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import LoginPage from '@/app/login/page'
import { AuthProvider } from '@/src/context/AuthContext'

describe('LoginPage', () => {
  beforeEach(() => {
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

  it('submits credentials and handles success', async () => {
    const mockFetch = jest.fn(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/auth/login')) {
        const body = JSON.parse(init?.body as string)
        return new Response(JSON.stringify({
          access_token: 'abc',
          refresh_token: 'ref',
          expires_in: 60,
          user: {
            id: 1,
            email: body.email,
            first_name: 'Test',
            last_name: 'User',
            full_name: 'Test User',
            role_id: 1,
            role_name: 'admin',
            status: 'active',
            verified: true
          }
        }), { status: 200 })
      }
      if (url.endsWith('/api/auth/me')) {
        return new Response(JSON.stringify({
          id: 1,
          email: 'test@example.com',
          first_name: 'Test',
          last_name: 'User',
          full_name: 'Test User',
          role_id: 1,
          role_name: 'admin',
          status: 'active',
          verified: true
        }), { status: 200 })
      }
      return new Response('{}', { status: 200 })
    }) as any
    global.fetch = mockFetch

    await act(async () => {
      render(<AuthProvider><LoginPage /></AuthProvider>)
    })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password1!' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
    })
    // AuthProvider monkey patches fetch, so ensure our mock saw a POST to /api/auth/login
    expect(mockFetch.mock.calls.some((call: any[]) => {
      const url = typeof call[0] === 'string' ? call[0] : call[0].toString()
      const init = call[1] as RequestInit | undefined
      return url.endsWith('/api/auth/login') && (init?.method === 'POST')
    })).toBe(true)
  })
})
