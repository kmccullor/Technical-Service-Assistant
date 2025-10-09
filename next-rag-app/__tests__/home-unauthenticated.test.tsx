import React from 'react'
import { render, screen, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import HomePage from '@/app/page'
import { AuthProvider } from '@/src/context/AuthContext'

// Minimal fetch mock returning 200 for /api/auth/me with no body -> treated as null profile
beforeEach(() => {
  delete (globalThis as any)._tsaFetchWrapped
  global.fetch = jest.fn(async (input) => {
    const url = typeof input === 'string' ? input : input.toString()
    if (url.endsWith('/api/auth/me')) {
      return new Response('{}', { status: 401 })
    }
    return new Response('{}', { status: 200 })
  }) as any
})

describe('HomePage unauthenticated view', () => {
  it('shows login and register links and no logout', async () => {
    await act(async () => {
      render(<AuthProvider><HomePage /></AuthProvider>)
    })
    expect(screen.getAllByText(/login/i)[0]).toBeInTheDocument()
    expect(screen.getAllByText(/register/i)[0]).toBeInTheDocument()
    expect(screen.queryByText(/logout/i)).not.toBeInTheDocument()
    expect(screen.getByText(/sign in to access the assistant/i)).toBeInTheDocument()
  })
})
