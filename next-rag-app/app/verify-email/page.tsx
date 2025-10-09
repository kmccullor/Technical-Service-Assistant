'use client'
import React, { useEffect, useState } from 'react'
import Link from 'next/link'

export default function VerifyEmailPage() {
  const [status, setStatus] = useState<'idle'|'verifying'|'success'|'error'>('idle')
  const [message, setMessage] = useState<string>('')
  const [token, setToken] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const t = params.get('token') || ''
    if (!t) {
      setStatus('error')
      setMessage('Missing verification token in URL.')
      return
    }
    setToken(t)
    ;(async () => {
      setStatus('verifying')
      try {
        const r = await fetch('/api/auth/verify-email', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: t }) })
        const data = await r.json().catch(() => ({}))
        if (r.ok && data.verified) {
          setStatus('success')
          setMessage('Email verified successfully! You can now log in.')
        } else {
          setStatus('error')
          setMessage(data?.detail || data?.message || 'Verification failed.')
        }
      } catch (e:any) {
        setStatus('error')
        setMessage(e?.message || 'Unexpected error during verification.')
      }
    })()
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-md w-full border rounded p-6 space-y-4 bg-background">
        <h1 className="text-xl font-semibold">Email Verification</h1>
        {status === 'verifying' && <p className="text-sm text-muted-foreground">Verifying your token...</p>}
        {status === 'success' && <p className="text-sm text-green-600">{message}</p>}
        {status === 'error' && <p className="text-sm text-red-600">{message}</p>}
        <div className="pt-2 flex gap-3">
          <Link href="/login" className="text-sm underline">Go to Login</Link>
          {status === 'error' && token && (
            <button onClick={() => { window.location.reload() }} className="text-sm underline">Retry</button>
          )}
        </div>
      </div>
    </div>
  )
}
