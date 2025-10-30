'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export default function ForgotPasswordPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!email) {
      setError('Email address is required')
      return
    }
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const res = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(typeof data.detail === 'string' ? data.detail : 'Failed to send reset email')
        return
      }
      setMessage('If an account exists for that email, reset instructions have been sent.')
      setTimeout(() => router.push('/login'), 2500)
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
          <h1 className="text-2xl font-semibold mb-2">Forgot Password</h1>
          <p className="text-sm text-muted-foreground">
            Enter your email address and we&apos;ll send you a reset link.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="forgot-email">Email</label>
            <input
              id="forgot-email"
              type="email"
              value={email}
              onChange={event => setEmail(event.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="you@example.com"
              required
            />
          </div>
          {error && <div className="text-sm text-red-600">{error}</div>}
          {message && <div className="text-sm text-green-600">{message}</div>}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? 'Sending...' : 'Send Reset Link'}
          </Button>
        </form>
        <div className="text-sm text-center text-muted-foreground space-y-1">
          <div>
            Remembered your password?{' '}
            <Link href="/login" className="text-primary underline">Back to login</Link>
          </div>
          <div>
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-primary underline">Register</Link>
          </div>
        </div>
      </Card>
    </div>
  )
}
