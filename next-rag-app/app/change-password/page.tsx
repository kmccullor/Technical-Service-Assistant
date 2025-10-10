'use client'
import React, { useState, useEffect } from 'react'
import { useAuth } from '@/src/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export default function ChangePasswordPage() {
  const { user, logout } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isForced, setIsForced] = useState(false)

  useEffect(() => {
    // Check if this is a forced password change
    if (user?.password_change_required) {
      setIsForced(true)
    }
  }, [user])

  const validatePassword = (password: string): string | null => {
    if (password.length < 8) {
      return 'Password must be at least 8 characters long'
    }
    if (!/[A-Z]/.test(password)) {
      return 'Password must contain at least one uppercase letter'
    }
    if (!/[a-z]/.test(password)) {
      return 'Password must contain at least one lowercase letter'
    }
    if (!/\d/.test(password)) {
      return 'Password must contain at least one digit'
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      return 'Password must contain at least one special character'
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    // Validate new password
    const passwordError = validatePassword(newPassword)
    if (passwordError) {
      setError(passwordError)
      return
    }

    // Check password confirmation
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match')
      return
    }

    // For forced changes, we don't need current password
    if (!isForced && !currentPassword) {
      setError('Current password is required')
      return
    }

    setLoading(true)

    try {
      const endpoint = isForced ? '/api/auth/force-change-password' : '/api/auth/change-password'
      const payload = isForced 
        ? { new_password: newPassword, confirm_password: confirmPassword }
        : { current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }

      const response = await fetch(`http://localhost:8008${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(payload)
      })

      const data = await response.json()

      if (response.ok) {
        setSuccess('Password changed successfully!')
        setTimeout(() => {
          if (isForced) {
            // For forced changes, redirect to home
            if (typeof window !== 'undefined') {
              window.location.href = '/'
            }
          } else {
            // For voluntary changes, stay on page
            setCurrentPassword('')
            setNewPassword('')
            setConfirmPassword('')
          }
        }, 2000)
      } else {
        setError(data.detail || 'Failed to change password')
      }
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }
  }

  if (!user) {
    if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }
    return null
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <Card className="p-8 w-full max-w-md space-y-6">
        <div>
          <h1 className="text-2xl font-semibold mb-2">
            {isForced ? 'Change Your Password' : 'Change Password'}
          </h1>
          {isForced ? (
            <p className="text-sm text-muted-foreground mb-4">
              You must change your password before continuing. Please choose a strong password.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Update your account password
            </p>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isForced && (
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="current-password">
                Current Password
              </label>
              <input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm bg-background"
                placeholder="Enter current password"
                required={!isForced}
              />
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="new-password">
              New Password
            </label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="Enter new password"
              required
            />
            <div className="text-xs text-muted-foreground">
              Password must contain at least 8 characters, including uppercase, lowercase, digit, and special character
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="confirm-password">
              Confirm New Password
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-background"
              placeholder="Confirm new password"
              required
            />
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="submit"
              disabled={loading}
              className="flex-1"
            >
              {loading ? 'Changing...' : 'Change Password'}
            </Button>
            
            {!isForced && (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  if (typeof window !== 'undefined') {
                    window.history.back()
                  }
                }}
                disabled={loading}
              >
                Cancel
              </Button>
            )}
          </div>
        </form>

        {isForced && (
          <div className="pt-4 border-t">
            <Button
              variant="outline"
              onClick={handleLogout}
              className="w-full"
            >
              Logout Instead
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}