'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ChatInterface } from '@/components/chat/chat-interface'
import { useAuth } from '@/src/context/AuthContext'
import Link from 'next/link'
import { Sidebar } from '@/components/layout/sidebar'
import { UserMenu } from '@/components/layout/user-menu'

export default function HomePage() {
  const [currentConversationId, setCurrentConversationId] = useState<number | undefined>()
  const [conversationRefreshKey, setConversationRefreshKey] = useState(0)
  const [redirecting, setRedirecting] = useState(false)
  const { user, logout, loading } = useAuth()
  const router = useRouter()
  const passwordChangeRequired = user?.password_change_required
  const userEmail = user?.email

  // Handle password change redirect
  useEffect(() => {
    console.log('[HOME] Password change check:', {
      userEmail,
      passwordChangeRequired,
      redirecting
    })
    if (passwordChangeRequired && !redirecting) {
      console.log('[HOME] Redirecting to password change page')
      setRedirecting(true)
      router.push('/change-password')
    }
  }, [passwordChangeRequired, userEmail, router, redirecting])

  // Show loading state while auth is initializing
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  // Show redirecting state
  if (user?.password_change_required || redirecting) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground">Redirecting to password change...</p>
        </div>
      </div>
    )
  }

  const handleNewChat = () => {
    setCurrentConversationId(undefined)
  }

  const handleSelectConversation = (id: number) => {
    setCurrentConversationId(id)
  }

  const handleConversationCreated = (id: number) => {
    setCurrentConversationId(id)
    setConversationRefreshKey(prev => prev + 1)
  }

  const handleConversationActivity = () => {
    setConversationRefreshKey(prev => prev + 1)
  }

  const handleConversationDeleted = (id: number) => {
    if (currentConversationId === id) {
      setCurrentConversationId(undefined)
    }
    setConversationRefreshKey(prev => prev + 1)
  }

  return (
    <div className="flex h-screen">
      {user && (
        <Sidebar
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          currentConversationId={currentConversationId}
          refreshKey={conversationRefreshKey}
          onConversationDeleted={handleConversationDeleted}
        />
      )}
      <main className="flex-1 flex flex-col">
        <div className="border-b p-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Technical Services Assistant</h1>
            <p className="text-muted-foreground text-sm">{user ? 'Ask questions about your documents' : 'Sign in to access the assistant'}</p>
          </div>
          <div className="flex items-center gap-4">
            {user ? (
              <UserMenu />
            ) : (
              <div className="flex gap-3 text-sm">
                <Link href="/login" className="underline">Login</Link>
                <Link href="/register" className="underline">Register</Link>
              </div>
            )}
          </div>
        </div>
        {user ? (
          <ChatInterface
            conversationId={currentConversationId}
            onConversationCreated={handleConversationCreated}
            onConversationActivity={handleConversationActivity}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-4">
              <h2 className="text-xl font-medium">Welcome to Technical Service Assistant</h2>
              <p className="text-muted-foreground max-w-md">Authenticate to start secure, role-based retrieval augmented conversations. Your role will control access to private versus public knowledge.</p>
              <div className="flex gap-4 justify-center">
                <Link href="/login" className="underline">Login</Link>
                <Link href="/register" className="underline">Register</Link>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
