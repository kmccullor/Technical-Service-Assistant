'use client'

import React, { useCallback, useEffect, useState } from 'react'
import { Plus, MessageCircle, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/src/context/AuthContext'

interface SidebarProps {
  onNewChat: () => void
  onSelectConversation: (id: number) => void
  currentConversationId?: number
  refreshKey?: number
  onConversationDeleted?: (id: number) => void
}

interface ConversationSummary {
  id: number
  title: string
  createdAt: string | null
  updatedAt?: string | null
  lastReviewedAt?: string | null
}

export function Sidebar({ onNewChat, onSelectConversation, currentConversationId, refreshKey = 0, onConversationDeleted }: SidebarProps) {
  const [mounted, setMounted] = useState(false)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(false)
  const [selectedConversationIds, setSelectedConversationIds] = useState<Set<number>>(new Set())
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false })
  const { accessToken } = useAuth()

  useEffect(() => {
    setMounted(true)
  }, [])

  const loadConversations = useCallback(async () => {
    if (!accessToken) {
      setConversations([])
      return
    }
    try {
      setConversationsLoading(true)
      const res = await fetch('/api/conversations?limit=30', {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: 'no-store',
      })
      if (!res.ok) {
        if (res.status === 401) {
          setConversations([])
          return
        }
        let detail = ''
        try {
          const err = await res.json()
          detail = err?.error || err?.detail || ''
        } catch {
          /* ignore */
        }
        throw new Error(detail || `Failed to load conversations (status ${res.status})`)
      }
      const responseData = await res.json()
      if (!responseData || !Array.isArray(responseData.conversations)) {
        setConversations([])
        return
      }
      const mapped = responseData.conversations.map((item: any) => ({
        id: item.id,
        title: item.title ?? 'Untitled conversation',
        createdAt: (item.createdAt ?? item.created_at ?? null) as string | null,
        updatedAt: (item.updatedAt ?? item.updated_at ?? null) as string | null,
        lastReviewedAt: (item.lastReviewedAt ?? item.last_reviewed_at ?? null) as string | null,
      }))
      setConversations(mapped)
    } catch (error) {
      console.error('[Conversations] fetch error:', error)
      setConversations([])
    } finally {
      setConversationsLoading(false)
    }
  }, [accessToken])

  useEffect(() => {
    loadConversations()
  }, [loadConversations, refreshKey])

  const toggleConversationSelection = (id: number) => {
    setSelectedConversationIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const toggleSelectAllConversations = () => {
    setSelectedConversationIds((prev) => {
      const next = new Set(prev)
      const everySelected = conversations.length > 0 && conversations.every((conv) => next.has(conv.id))
      if (everySelected) {
        conversations.forEach((conv) => next.delete(conv.id))
      } else {
        conversations.forEach((conv) => next.add(conv.id))
      }
      return next
    })
  }

  const handleDeleteSelectedConversations = async () => {
    if (!accessToken || selectedConversationIds.size === 0) return
    const ids = Array.from(selectedConversationIds)
    if (!window.confirm(`Delete ${ids.length} conversation${ids.length > 1 ? 's' : ''}? This action cannot be undone.`)) {
      return
    }
    try {
      for (const id of ids) {
        const res = await fetch(`/api/conversations/${id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        if (!res.ok && res.status !== 204) {
          let detail = ''
          try {
            const err = await res.json()
            detail = err?.error || err?.detail || ''
          } catch {
            /* ignore */
          }
          throw new Error(detail || `Failed to delete conversation ${id} (status ${res.status})`)
        }
        onConversationDeleted?.(id)
      }
      setSelectedConversationIds(new Set())
      loadConversations()
    } catch (error) {
      console.error('Failed to delete selected conversations:', error)
      alert('Failed to delete some conversations. Please try again.')
    }
  }

  const handleConversationRightClick = (e: React.MouseEvent, id: number) => {
    e.preventDefault()
    if (!selectedConversationIds.has(id)) {
      setSelectedConversationIds(new Set([id]))
    }
    setContextMenu({ x: e.clientX, y: e.clientY, visible: true })
  }

  const closeContextMenu = () => setContextMenu({ ...contextMenu, visible: false })

  if (!mounted) {
    return (
      <div className="flex flex-col">
        <div className="px-4 pb-2">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Recent Conversations</h3>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">Recent Conversations</h3>
        <Button size="sm" variant="outline" onClick={onNewChat} className="flex items-center gap-1">
          <Plus className="h-4 w-4" />
          <span className="text-xs">New</span>
        </Button>
      </div>
      {conversations.length > 0 && (
        <div className="px-4 pb-2 flex items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="h-3 w-3"
              checked={conversations.length > 0 && conversations.every((conv) => selectedConversationIds.has(conv.id))}
              onChange={(e) => {
                e.stopPropagation()
                toggleSelectAllConversations()
              }}
            />
            <span>Select all</span>
          </label>
          {selectedConversationIds.size > 0 && (
            <Button size="sm" variant="destructive" onClick={handleDeleteSelectedConversations} className="text-xs px-2 py-1 h-auto">
              Delete ({selectedConversationIds.size})
            </Button>
          )}
        </div>
      )}
      <div className="px-2 space-y-2 overflow-y-auto">
        {conversationsLoading ? (
          <div className="px-1 py-2 text-sm text-muted-foreground">Loading conversations...</div>
        ) : conversations.length === 0 ? (
          <div className="px-1 py-2 text-sm text-muted-foreground">No conversations yet. Start a new chat to begin.</div>
        ) : (
          conversations.map((conversation) => {
            const latestTimestamp = conversation.updatedAt ?? conversation.createdAt
            const formattedDate = latestTimestamp ? new Date(latestTimestamp).toLocaleString() : ''
            return (
              <div
                key={conversation.id}
                className={`w-full border rounded p-3 ${selectedConversationIds.has(conversation.id) ? 'bg-blue-50 border-blue-200' : 'border-transparent'} ${currentConversationId === conversation.id ? 'bg-secondary' : ''}`}
              >
                <div className="flex items-start gap-2 w-full">
                  <div className="flex-shrink-0 w-5 flex items-center justify-center">
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      checked={selectedConversationIds.has(conversation.id)}
                      onChange={(e) => {
                        e.stopPropagation()
                        toggleConversationSelection(conversation.id)
                      }}
                    />
                  </div>
                  <button
                    className="flex-1 text-left hover:bg-transparent"
                    onClick={() => {
                      onSelectConversation(conversation.id)
                      setSelectedConversationIds(new Set())
                    }}
                    onContextMenu={(e) => handleConversationRightClick(e, conversation.id)}
                  >
                    <div className="flex items-start gap-2 w-full">
                      <MessageCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="truncate text-sm">{conversation.title}</div>
                        <div className="text-xs text-muted-foreground">{formattedDate}</div>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    className="ml-2 text-muted-foreground hover:text-destructive transition-colors flex-shrink-0"
                    onClick={async (event) => {
                      event.stopPropagation()
                      if (!window.confirm('Delete this conversation? This action cannot be undone.')) {
                        return
                      }
                      try {
                        if (!accessToken) {
                          throw new Error('Not authenticated')
                        }
                        const res = await fetch(`/api/conversations/${conversation.id}`, {
                          method: 'DELETE',
                          headers: { Authorization: `Bearer ${accessToken}` },
                        })
                        if (!res.ok && res.status !== 204) {
                          let detail = ''
                          try {
                            const err = await res.json()
                            detail = err?.error || err?.detail || ''
                          } catch {
                            /* ignore */
                          }
                          throw new Error(detail || `Failed to delete conversation (status ${res.status})`)
                        }
                        onConversationDeleted?.(conversation.id)
                        loadConversations()
                      } catch (error) {
                        console.error('Failed to delete conversation:', error)
                        alert('Failed to delete conversation. Please try again.')
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                    <span className="sr-only">Delete conversation</span>
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {contextMenu.visible && (
        <div
          className="fixed z-50 bg-white border border-gray-300 rounded shadow-lg py-1"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={closeContextMenu}
        >
          <button
            className="w-full text-left px-4 py-2 hover:bg-gray-100 text-red-600"
            onClick={() => {
              handleDeleteSelectedConversations()
              closeContextMenu()
            }}
          >
            Delete Selected Conversations
          </button>
        </div>
      )}
      {contextMenu.visible && <div className="fixed inset-0 z-40" onClick={closeContextMenu} />}
    </div>
  )
}
