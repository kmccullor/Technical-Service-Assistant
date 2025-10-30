'use client'

import React, { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

function ResetPasswordForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [token, setToken] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const initialToken = searchParams.get('token')
    if (initialToken) {
      setToken(initialToken)
    }
  }, [searchParams])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!token) {
      setError('Reset token is required')
      return
    }
    if (!password || password.length < 8) {
      setError('Password must be at least 8 characters long')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(typeof data.detail === 'string' ? data.detail : 'Failed to reset password')
        return
      }
      setMessage('Password updated. Redirecting to login...')
      setTimeout(() => router.push('/login'), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <Card className="p-8 w-full max-w-md space-y-6">
        <div>
          <h1 className="text-2xl font-semibold mb-2">Reset Password</h1>
          <p className="text-sm text-muted-foreground">
            Paste your reset token and choose a new password.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="reset-token">Reset Token</label>
            <input
              id="reset-token"
              type="text"
              value={token}
              onChange={event => setToken(event.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="Paste token from email"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="reset-password">New Password</label>
            <input
              id="reset-password"
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="••••••••"
              required
              minLength={8}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="reset-password-confirm">Confirm Password</label>
            <input
              id="reset-password-confirm"
              type="password"
              value={confirmPassword}
              onChange={event => setConfirmPassword(event.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="••••••••"
              required
              minLength={8}
            />
          </div>
          {error && <div className="text-sm text-red-600">{error}</div>}
          {message && <div className="text-sm text-green-600">{message}</div>}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? 'Updating...' : 'Update Password'}
          </Button>
        </form>
        <div className="text-sm text-center text-muted-foreground">
          Return to{' '}
          <Link href="/login" className="text-primary underline">login</Link>
        </div>
      </Card>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <Card className="p-8 w-full max-w-md text-center">
          <p className="text-sm text-muted-foreground">Loading reset form...</p>
        </Card>
      </div>
    }>
      <ResetPasswordForm />
    </Suspense>
  )
}
