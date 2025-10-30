import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import ResetPasswordPage from '@/app/reset-password/page'

const mockPush = jest.fn()
const mockSearchParamsGet = jest.fn()

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({
    get: mockSearchParamsGet,
  }),
}))

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    mockPush.mockReset()
    mockSearchParamsGet.mockReset()
    mockSearchParamsGet.mockReturnValue('token-abc')
  })

  it('submits token and new password to reset endpoint', async () => {
    const mockFetch = jest.fn(async () => new Response(JSON.stringify({ success: true }), { status: 200 })) as any
    global.fetch = mockFetch

    await act(async () => {
      render(<ResetPasswordPage />)
    })

    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Password1!' } })
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Password1!' } })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /update password/i }))
    })

    expect(mockFetch).toHaveBeenCalledWith('/api/auth/reset-password', expect.objectContaining({
      method: 'POST',
    }))
  })
})
