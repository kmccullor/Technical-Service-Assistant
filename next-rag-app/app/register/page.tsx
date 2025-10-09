'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/src/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export default function RegisterPage() {
  const { register, loading, error } = useAuth()
  const replace = (path: string) => {
    if (typeof window !== 'undefined') {
      try { window.location.href = path } catch(_) {}
    }
  }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    if (!email || !password) {
      setFormError('Email and password required')
      return
    }
    const ok = await register({ email, password, first_name: firstName, last_name: lastName })
    if (ok) {
      setSuccess(true)
  setTimeout(() => replace('/login'), 2000)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <Card className="p-8 w-full max-w-md space-y-6">
        <div>
          <h1 className="text-2xl font-semibold mb-2">Create Account</h1>
          <p className="text-sm text-muted-foreground">Register to use the Technical Service Assistant</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="you@example.com"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">First Name</label>
              <input
                value={firstName}
                onChange={e => setFirstName(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm bg-background"
                placeholder="Jane"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Last Name</label>
              <input
                value={lastName}
                onChange={e => setLastName(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm bg-background"
                placeholder="Doe"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="StrongPassword123!"
              required
            />
          </div>
          {(formError || error) && (
            <div className="text-sm text-red-600">
              {formError || error}
            </div>
          )}
          {success && (
            <div className="text-sm text-green-600">Registration successful! Redirecting to login...</div>
          )}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? 'Registering...' : 'Register'}
          </Button>
        </form>
        <div className="text-sm text-center text-muted-foreground">
          Already have an account?{' '}
          <Link href="/login" className="text-primary underline">Sign In</Link>
        </div>
      </Card>
    </div>
  )
}
