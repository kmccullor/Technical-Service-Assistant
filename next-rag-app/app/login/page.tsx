'use client'
import React, { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/src/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export default function LoginPage() {
  const { login, loading, error, user } = useAuth()
  const replace = (path: string) => {
    if (typeof window !== 'undefined') {
      try { window.location.href = path; } catch(_) {}
    }
  }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  if (user) {
    console.log('[LOGIN] User already logged in, redirecting to home:', user.email)
    replace('/')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    console.log('[LOGIN] Form submitted for email:', email)
    setFormError(null)
    if (!email || !password) {
      console.log('[LOGIN] Missing email or password')
      setFormError('Email and password required')
      return
    }
    console.log('[LOGIN] Calling login function')
    const ok = await login(email, password)
    console.log('[LOGIN] Login result:', ok)
    if (ok) {
      console.log('[LOGIN] Login successful, redirecting to home')
      replace('/')
    } else {
      console.log('[LOGIN] Login failed')
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <Card className="p-8 w-full max-w-md space-y-6">
        <div>
          <h1 className="text-2xl font-semibold mb-2">Sign In</h1>
          <p className="text-sm text-muted-foreground">Access the Technical Service Assistant</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="you@example.com"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="••••••••"
              required
            />
          </div>
          {(formError || error) && (
            <div className="text-sm text-red-600">
              {formError || error}
            </div>
          )}
          <div className="text-right text-sm">
            <Link href="/forgot-password" className="text-primary underline">
              Forgot password?
            </Link>
          </div>
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>
        <div className="text-sm text-center text-muted-foreground">
          Need an account?{' '}
          <Link href="/register" className="text-primary underline">Register</Link>
        </div>
      </Card>
    </div>
  )
}
