import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import ForgotPasswordPage from '@/app/forgot-password/page'

const mockPush = jest.fn()

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    mockPush.mockReset()
  })

  it('submits email to the forgot-password endpoint', async () => {
    const mockFetch = jest.fn(async () => new Response(JSON.stringify({ success: true }), { status: 200 })) as any
    global.fetch = mockFetch

    await act(async () => {
      render(<ForgotPasswordPage />)
    })

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /send reset link/i }))
    })

    expect(mockFetch).toHaveBeenCalledWith('/api/auth/forgot-password', expect.objectContaining({
      method: 'POST',
    }))
  })
})
