'use client'

import React, { useState } from 'react'
import { ChatInterface } from '@/components/chat/chat-interface'
import { useAuth } from '@/src/context/AuthContext'
import Link from 'next/link'
import { Sidebar } from '@/components/layout/sidebar'

export default function HomePage() {
  const [currentConversationId, setCurrentConversationId] = useState<number | undefined>()
  const { user, logout } = useAuth()

  const handleNewChat = () => {
    setCurrentConversationId(undefined)
  }

  const handleSelectConversation = (id: number) => {
    setCurrentConversationId(id)
  }

  return (
    <div className="flex h-screen">
      {user && (
        <Sidebar
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          currentConversationId={currentConversationId}
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
              <>
                <span className="text-sm text-muted-foreground">{user.full_name} <span className="ml-2 px-2 py-0.5 rounded bg-secondary text-xs uppercase">{user.role_name || 'role ' + user.role_id}</span></span>
                <button onClick={logout} className="text-sm underline">Logout</button>
              </>
            ) : (
              <div className="flex gap-3 text-sm">
                <Link href="/login" className="underline">Login</Link>
                <Link href="/register" className="underline">Register</Link>
              </div>
            )}
          </div>
        </div>
        {user ? (
          <ChatInterface conversationId={currentConversationId} />
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