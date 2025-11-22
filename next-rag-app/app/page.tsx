'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

import { ChatInterface } from '@/components/chat/chat-interface'
import type { ChatMessage } from '@/components/chat/types'
import { useAuth } from '@/src/context/AuthContext'
import { Sidebar } from '@/components/layout/sidebar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog-client'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Key, LogOut, PanelLeftClose, PanelLeftOpen, Settings } from 'lucide-react'

const SYSTEM_PROMPTS = [
  'Stay focused on Salesforce case research for Sensus AMI products and infrastructure.',
  'Reference the Postgres + pgvector technical knowledge base whenever possible.',
  'Surface analysis, diagnostics, and recommended next steps for engineers and support.'
]

export default function HomePage() {
  const [currentConversationId, setCurrentConversationId] = useState<number | undefined>()
  const [conversationRefreshKey, setConversationRefreshKey] = useState(0)
  const [redirecting, setRedirecting] = useState(false)
  const { user, loading, logout } = useAuth()
  const router = useRouter()
  const passwordChangeRequired = user?.password_change_required

  const [persona, setPersona] = useState<'friendly' | 'formal'>('friendly')
  const [tone, setTone] = useState<'concise' | 'verbose'>('concise')
  const [customPrompt, setCustomPrompt] = useState(
    'You are a Salesforce research analyst for the Sensus AMI product family. Use Postgres + pgvector knowledge to provide evidence-backed analysis, diagnostics, and recommendations.'
  )
  const [roleView, setRoleView] = useState<string>(user?.role_name ?? 'guest')
  const [canvasMessages, setCanvasMessages] = useState<ChatMessage[]>([])
  const [sidebarWidth, setSidebarWidth] = useState(280)
  const [sidebarVisible, setSidebarVisible] = useState(true)
  const [isResizingSidebar, setIsResizingSidebar] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const layoutRef = useRef<HTMLDivElement>(null)
  const isAdmin = (user?.role_name ?? '').toLowerCase() === 'admin'

  const lastAssistantMessage = useMemo(
    () => canvasMessages.slice().reverse().find((message) => message.role === 'assistant'),
    [canvasMessages]
  )

  const lastUserMessage = useMemo(
    () => canvasMessages.slice().reverse().find((message) => message.role === 'user'),
    [canvasMessages]
  )

  const memoryEntries = useMemo(() => {
    return canvasMessages
      .filter((message) => message.role === 'user')
      .slice(-4)
      .map((message, index) => ({
        id: `${message.id}-${index}`,
        title: message.content.split('\n')[0] || `Query ${index + 1}`,
        snippet: message.content,
        timestamp: message.timestamp.toLocaleString(),
      }))
  }, [canvasMessages])

  const sources = useMemo(() => {
    try {
      const entries: Record<string, { title: string; summary: string; source: string; url?: string }> = {}
      const isHttp = (value: unknown): value is string =>
        typeof value === 'string' && value.startsWith('http')

      canvasMessages.forEach((message) => {
        if (!Array.isArray(message.citations)) {
          return
        }

        message.citations.forEach((citation, idx) => {
          if (!citation || typeof citation !== 'object') {
            return
          }

          const id = typeof (citation as any).id === 'string' && (citation as any).id
            ? (citation as any).id
            : `${message.id}-${idx}`
          const title = typeof (citation as any).title === 'string' && (citation as any).title
            ? (citation as any).title
            : 'Untitled source'
          const rawContent = typeof (citation as any).content === 'string' ? (citation as any).content : ''
          const summary = rawContent.length > 160 ? `${rawContent.slice(0, 160)}…` : rawContent || 'No excerpt available'
          const source = typeof (citation as any).source === 'string' ? (citation as any).source : ''
          const url = isHttp(source) ? source : undefined

          if (!entries[id]) {
            entries[id] = {
              title,
              summary,
              source: source || 'Unknown source',
              url,
            }
          }
        })
      })
      return Object.entries(entries).slice(0, 6).map(([id, entry]) => ({
        id,
        ...entry,
      }))
    } catch (err) {
      console.error('Failed to build sources:', err)
      return []
    }
  }, [canvasMessages])

  const insightPreview = lastAssistantMessage?.content || 'Create a Salesforce case question to kick off the research canvas.'
  const citationsCount = lastAssistantMessage?.citations?.length ?? 0
  const gridTemplateColumns = sidebarVisible ? `${sidebarWidth}px 8px minmax(0, 1fr)` : 'minmax(0, 1fr)'
  const navigationCards = [
    {
      key: 'admin',
      label: 'Admin Dashboard',
      href: '/admin',
      description: 'RBAC controls & telemetry',
      disabled: !isAdmin,
    },
    {
      key: 'canvas',
      label: 'Canvas Dashboard',
      href: '/canvas-settings',
      description: 'Persona and tone tuning',
      disabled: false,
    },
    {
      key: 'documents',
      label: 'Document Dashboard',
      href: '/docs',
      description: 'Explore ingested corpus',
      disabled: false,
    },
  ]

  useEffect(() => {
    if (user?.role_name) {
      setRoleView(user.role_name)
    }
  }, [user?.role_name])

  const handleSidebarResizeStart = () => {
    if (!sidebarVisible) return
    setIsResizingSidebar(true)
  }

  useEffect(() => {
    if (!isResizingSidebar) return
    const handleMouseMove = (event: MouseEvent) => {
      if (!layoutRef.current) return
      const rect = layoutRef.current.getBoundingClientRect()
      const minWidth = 220
      const maxWidth = 420
      const nextWidth = Math.min(Math.max(event.clientX - rect.left, minWidth), maxWidth)
      setSidebarWidth(nextWidth)
    }
    const handleMouseUp = () => setIsResizingSidebar(false)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizingSidebar, sidebarVisible])

  useEffect(() => {
    if (passwordChangeRequired && !redirecting) {
      setRedirecting(true)
      router.push('/change-password')
    }
  }, [passwordChangeRequired, redirecting, router])

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
    setConversationRefreshKey((prev) => prev + 1)
  }

  const handleConversationActivity = () => {
    setConversationRefreshKey((prev) => prev + 1)
  }

  const handleConversationDeleted = (id: number) => {
    if (currentConversationId === id) {
      setCurrentConversationId(undefined)
    }
    setConversationRefreshKey((prev) => prev + 1)
  }

  const handlePersonaChange = (value: 'friendly' | 'formal') => {
    setPersona(value)
  }

  const handleToneChange = (value: 'concise' | 'verbose') => {
    setTone(value)
  }

  return (
    <div className="min-h-screen bg-slate-100 py-4 px-2 sm:px-4">
      {!sidebarVisible && user && (
        <Button
          variant="outline"
          size="sm"
          className="fixed left-4 top-6 z-40 flex items-center gap-2 rounded-full border-slate-300 bg-white"
          onClick={() => setSidebarVisible(true)}
        >
          <PanelLeftOpen className="h-4 w-4" /> Show panel
        </Button>
      )}
      {user ? (
        <div
          ref={layoutRef}
          className="relative mx-auto grid h-[calc(100vh-2rem)] w-full max-w-[1500px] gap-6 rounded-[48px] border border-slate-200 bg-white shadow-2xl"
          style={{ gridTemplateColumns }}
        >
          {sidebarVisible && (
            <>
              <aside className="relative flex flex-col gap-4 bg-slate-50/60 p-4">
                <button
                  type="button"
                  className="absolute right-4 top-4 inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 hover:text-slate-900"
                  onClick={() => setSidebarVisible(false)}
                  aria-label="Collapse sidebar"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="w-full rounded-[32px] border border-slate-200 bg-white/80 p-4 text-left shadow-inner transition hover:border-primary/50"
                    >
                      <p className="text-xs uppercase tracking-wide text-slate-500">User Info</p>
                      <p className="text-lg font-semibold text-slate-900">{user.full_name}</p>
                      <p className="text-xs text-slate-500">{user.email}</p>
                      <p className="text-xs text-slate-500">Role: {user.role_name || 'Guest'}</p>
                      <p className="mt-2 text-[11px] text-primary underline">Account menu</p>
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-56">
                    <DropdownMenuItem asChild>
                      <Link href="/change-password" className="flex items-center cursor-pointer">
                        <Key className="mr-2 h-4 w-4" />
                        <span>Change password</span>
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={logout} className="flex items-center cursor-pointer text-red-600 focus:text-red-700">
                      <LogOut className="mr-2 h-4 w-4" />
                      <span>Logout</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <div className="space-y-3">
                  {navigationCards.map((card) => {
                    if (card.disabled || !card.href) {
                      return (
                        <div
                          key={card.key}
                          className="rounded-[28px] border border-dashed border-slate-200/60 bg-white/60 px-4 py-3 text-sm text-slate-500"
                          aria-disabled="true"
                        >
                          <p className="font-semibold text-slate-700">{card.label}</p>
                          <p className="text-xs">{card.description}</p>
                          <p className="mt-1 text-[11px]">Admin access required</p>
                        </div>
                      )
                    }
                    return (
                      <Link
                        key={card.key}
                        href={card.href}
                        className="block rounded-[28px] border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-800 shadow-sm transition hover:border-primary/50 hover:text-primary"
                      >
                        <p>{card.label}</p>
                        <p className="text-xs font-normal text-slate-500">{card.description}</p>
                      </Link>
                    )
                  })}
                </div>
                <div className="flex flex-1 flex-col rounded-[32px] border border-slate-200 bg-white p-4 shadow-inner">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-600">Recent Conversations</p>
                    <button className="text-xs font-medium text-primary underline-offset-2 hover:underline" onClick={handleNewChat}>
                      New
                    </button>
                  </div>
                  <div className="mt-3 flex-1 overflow-hidden rounded-[24px] border border-dashed border-slate-200 bg-slate-50 p-2">
                    <div className="h-full overflow-y-auto pr-1">
                      <Sidebar
                        onNewChat={handleNewChat}
                        onSelectConversation={handleSelectConversation}
                        currentConversationId={currentConversationId}
                        refreshKey={conversationRefreshKey}
                        onConversationDeleted={handleConversationDeleted}
                      />
                    </div>
                  </div>
                </div>
                <div className="rounded-[32px] border border-slate-200 bg-white p-4 shadow-inner">
                  <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
                    <DialogTrigger asChild>
                      <Button variant="ghost" className="w-full justify-start">
                        <Settings className="h-4 w-4 mr-2" />
                        Settings
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-md">
                      <DialogHeader>
                        <DialogTitle>System Settings</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 text-sm text-muted-foreground">
                        <div>
                          <p className="font-medium text-foreground">System Information</p>
                          <p>Documents are indexed via the documents console. Admins can manage uploads there.</p>
                        </div>
                        <div>
                          <p className="font-medium text-foreground">Version</p>
                          <p>Canvas build 1.0 · Last refreshed this session.</p>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </aside>
              <div className="hidden sm:flex items-stretch">
                <div
                  className="mx-auto h-full w-1 cursor-col-resize rounded-full bg-slate-200 transition-colors hover:bg-slate-400"
                  onMouseDown={handleSidebarResizeStart}
                  aria-label="Resize sidebar"
                />
              </div>
            </>
          )}
          <section className="grid grid-rows-[auto_minmax(0,1fr)_auto] gap-4 p-6">
            <div className="rounded-[36px] border border-slate-200 bg-white/90 px-6 py-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Salesforce Research Canvas</p>
                  <h1 className="text-2xl font-semibold text-slate-900">Technical Services Assistant</h1>
                  <p className="text-sm text-slate-500">
                    Guidance focused on Sensus AMI cases with evidence sourced from the Postgres + pgvector knowledge base.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge variant="outline">Role view: {roleView}</Badge>
                  <Badge variant="outline">Persona: {persona}</Badge>
                  <Badge variant="outline">Tone: {tone}</Badge>
                </div>
              </div>
            </div>
            <div className="rounded-[36px] border border-slate-200 bg-gradient-to-b from-white to-slate-50 p-4 shadow-inner">
              <div className="flex h-full flex-col">
                <div className="rounded-[24px] border border-dashed border-slate-200/80 bg-white/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
                  Response Dialog
                </div>
                <div className="mt-3 flex-1 overflow-hidden rounded-[28px] border border-slate-100 bg-white">
                  <div className="h-full">
                    <ChatInterface
                      conversationId={currentConversationId}
                      onConversationCreated={handleConversationCreated}
                      onConversationActivity={handleConversationActivity}
                      onMessagesChange={setCanvasMessages}
                      persona={persona}
                      tone={tone}
                      customPrompt={customPrompt}
                      composerPortalId="chat-input-panel"
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="rounded-[32px] border border-slate-200 bg-white/95 p-5 shadow-sm">
              <div className="text-xs uppercase tracking-[0.4em] text-slate-500">Chat Input</div>
              <div id="chat-input-panel" className="mt-4"></div>
            </div>
          </section>
        </div>
      ) : (
        <div className="flex min-h-screen items-center justify-center p-4">
          <div className="max-w-md space-y-4 text-center">
            <h2 className="text-xl font-medium">Welcome to Technical Service Assistant</h2>
            <p className="text-sm text-muted-foreground">
              Authenticate to start secure, role-based retrieval augmented conversations. Your role will control access to private versus public knowledge.
            </p>
            <div className="flex justify-center gap-4">
              <Link href="/login" className="underline">
                Login
              </Link>
              <Link href="/register" className="underline">
                Register
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
