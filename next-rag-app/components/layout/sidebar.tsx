
'use client'
import React from 'react'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/src/context/AuthContext'
import { Plus, MessageCircle, FileText, Search, Settings, X, Upload, Shield, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from '@/components/ui/dialog-client'

type DocumentFilterKey = 'type' | 'product' | 'version' | 'privacy'

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
  const [stats, setStats] = useState({ documents: 0, chunks: 0 })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [documentsOpen, setDocumentsOpen] = useState(false)
  const [documents, setDocuments] = useState<any[]>([])
  const [filteredDocuments, setFilteredDocuments] = useState<any[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [documentsError, setDocumentsError] = useState<string | null>(null)
  const [documentSearch, setDocumentSearch] = useState("")
  const [documentFilters, setDocumentFilters] = useState({
    type: [] as string[],
    product: [] as string[],
    version: [] as string[],
    privacy: [] as string[],
  })
  const [documentFilterOptions, setDocumentFilterOptions] = useState({
    types: [] as string[],
    products: [] as string[],
    versions: [] as string[],
    privacies: [] as string[],
  })
  const { accessToken, user } = useAuth()

  // Ensure component is mounted before rendering dialogs
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
      const data = await res.json()
      if (!Array.isArray(data)) {
        setConversations([])
        return
      }
      const mapped = data.map((item: any) => ({
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
    // Placeholder stats - can be replaced with a real API call later
    setStats({ documents: 42, chunks: 1234 })
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations, refreshKey])

  useEffect(() => {
    if (documentsOpen) {
      setDocumentsLoading(true)
      setDocumentsError(null)
      const controller = new AbortController()
      const fetchDocuments = async () => {
        try {
          const res = await fetch('/api/documents/list', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
            },
            body: JSON.stringify({ limit: 50, offset: 0 }),
            signal: controller.signal
          })
          if (!res.ok) {
            let detail = ''
            try {
              const errJson = await res.json()
              detail = errJson.detail || JSON.stringify(errJson)
            } catch {}
            throw new Error(`Failed to fetch documents (status ${res.status}) ${detail}`.trim())
          }
          const data = await res.json()
          const docs = data.documents || []
          setDocuments(docs)
          setFilteredDocuments(docs)
        } catch (err: any) {
          if (err.name === 'AbortError') return
          console.error('[Documents] fetch error:', err)
            setDocumentsError(err.message || 'Unknown error')
        } finally {
          setDocumentsLoading(false)
        }
      }
      fetchDocuments()
      return () => controller.abort()
    }
  }, [documentsOpen, accessToken])

  useEffect(() => {
    if (!documentsOpen) return
    const nextOptions = {
      types: new Set<string>(),
      products: new Set<string>(),
      versions: new Set<string>(),
      privacies: new Set<string>(),
    }
    documents.forEach((doc) => {
      if (doc.document_type) nextOptions.types.add(doc.document_type)
      if (doc.product_name) nextOptions.products.add(doc.product_name)
      if (doc.product_version) nextOptions.versions.add(doc.product_version)
      if (doc.privacy_level) nextOptions.privacies.add(doc.privacy_level)
    })
    setDocumentFilterOptions({
      types: Array.from(nextOptions.types).sort(),
      products: Array.from(nextOptions.products).sort(),
      versions: Array.from(nextOptions.versions).sort(),
      privacies: Array.from(nextOptions.privacies).sort(),
    })
    setDocumentFilters(prev => ({
      type: prev.type.filter((value) => nextOptions.types.has(value)),
      product: prev.product.filter((value) => nextOptions.products.has(value)),
      version: prev.version.filter((value) => nextOptions.versions.has(value)),
      privacy: prev.privacy.filter((value) => nextOptions.privacies.has(value)),
    }))
  }, [documentsOpen, documents])
  useEffect(() => {
    if (!documentsOpen) return
    const term = documentSearch.trim().toLowerCase()
    setFilteredDocuments(
      documents.filter((doc) => {
        const parts = [
          doc.file_name,
          doc.document_type,
          doc.product_name,
          doc.product_version,
          doc.privacy_level,
        ]
          .filter(Boolean)
          .map((value: string) => value.toString().toLowerCase())
        const matchesSearch = term ? parts.some((value) => value.includes(term)) : true
        if (!matchesSearch) return false
        if (documentFilters.type.length && (!doc.document_type || !documentFilters.type.includes(doc.document_type))) return false
        if (documentFilters.product.length && (!doc.product_name || !documentFilters.product.includes(doc.product_name))) return false
        if (documentFilters.version.length && (!doc.product_version || !documentFilters.version.includes(doc.product_version))) return false
        if (documentFilters.privacy.length && (!doc.privacy_level || !documentFilters.privacy.includes(doc.privacy_level))) return false
        return true
      })
    )
  }, [documentSearch, documents, documentsOpen, documentFilters])

  useEffect(() => {
    if (!documentsOpen) {
      setDocumentSearch("")
      setDocumentFilters({
        type: [],
        product: [],
        version: [],
        privacy: [],
      })
    }
  }, [documentsOpen])

  const toggleDocumentFilter = (key: DocumentFilterKey, value: string) => {
    setDocumentFilters((prev) => {
      const current = new Set(prev[key])
      if (current.has(value)) {
        current.delete(value)
      } else {
        current.add(value)
      }
      return { ...prev, [key]: Array.from(current) }
    })
  }

  // Don't render dialogs until component is mounted (prevents hydration issues)
  if (!mounted) {
    return (
      <div className="w-64 bg-muted/30 border-r flex flex-col">
        <div className="p-4 border-b">
          <Button variant="ghost" className="w-full justify-start" disabled>
            <FileText className="h-4 w-4 mr-2" />
            Documents
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 pb-2">
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Recent Conversations</h3>
          </div>
        </div>
        <div className="p-4 border-t">
          <Button variant="ghost" className="w-full justify-start" disabled>
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="w-64 bg-muted/30 border-r flex flex-col">
      {/* Header */}
      <div className="p-4 border-b">
        <Dialog open={documentsOpen} onOpenChange={setDocumentsOpen}>
          <DialogTrigger asChild>
            <Button variant="ghost" className="w-full justify-start">
              <FileText className="h-4 w-4 mr-2" />
              Documents
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Documents</DialogTitle>
              <DialogDescription>View and manage uploaded documents.</DialogDescription>
            </DialogHeader>
            {documentsLoading ? (
              <div className="py-2 text-muted-foreground text-sm">Loading documents...</div>
            ) : documentsError ? (
              <div className="py-2 text-red-500 text-sm">Error: {documentsError}</div>
            ) : (
              <div className="py-2 space-y-2">
                <div className="flex flex-col gap-2">
                  <input
                    type="text"
                    value={documentSearch}
                    onChange={(e) => setDocumentSearch(e.target.value)}
                    placeholder="Search documents"
                    className="w-full border rounded px-2 py-1 text-sm"
                  />
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="border rounded px-2 py-2">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Type</p>
                      <div className="flex flex-col gap-1 max-h-24 overflow-y-auto pr-1">
                        {documentFilterOptions.types.length === 0 ? (
                          <span className="text-xs text-muted-foreground">No types available</span>
                        ) : (
                          documentFilterOptions.types.map((value) => (
                            <label key={value} className="flex items-center gap-2 text-xs">
                              <input
                                type="checkbox"
                                checked={documentFilters.type.includes(value)}
                                onChange={() => toggleDocumentFilter('type', value)}
                                className="h-3 w-3"
                              />
                              <span>{value}</span>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="border rounded px-2 py-2">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Product</p>
                      <div className="flex flex-col gap-1 max-h-24 overflow-y-auto pr-1">
                        {documentFilterOptions.products.length === 0 ? (
                          <span className="text-xs text-muted-foreground">No products available</span>
                        ) : (
                          documentFilterOptions.products.map((value) => (
                            <label key={value} className="flex items-center gap-2 text-xs">
                              <input
                                type="checkbox"
                                checked={documentFilters.product.includes(value)}
                                onChange={() => toggleDocumentFilter('product', value)}
                                className="h-3 w-3"
                              />
                              <span>{value}</span>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="border rounded px-2 py-2">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Version</p>
                      <div className="flex flex-col gap-1 max-h-24 overflow-y-auto pr-1">
                        {documentFilterOptions.versions.length === 0 ? (
                          <span className="text-xs text-muted-foreground">No versions available</span>
                        ) : (
                          documentFilterOptions.versions.map((value) => (
                            <label key={value} className="flex items-center gap-2 text-xs">
                              <input
                                type="checkbox"
                                checked={documentFilters.version.includes(value)}
                                onChange={() => toggleDocumentFilter('version', value)}
                                className="h-3 w-3"
                              />
                              <span>{value}</span>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="border rounded px-2 py-2">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Privacy</p>
                      <div className="flex flex-col gap-1 max-h-24 overflow-y-auto pr-1">
                        {documentFilterOptions.privacies.length === 0 ? (
                          <span className="text-xs text-muted-foreground">No privacy levels available</span>
                        ) : (
                          documentFilterOptions.privacies.map((value) => (
                            <label key={value} className="flex items-center gap-2 text-xs">
                              <input
                                type="checkbox"
                                checked={documentFilters.privacy.includes(value)}
                                onChange={() => toggleDocumentFilter('privacy', value)}
                                className="h-3 w-3"
                              />
                              <span>{value}</span>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="max-h-64 overflow-y-auto pr-2">
                  {documents.length === 0 ? (
                    <div className="py-2 text-muted-foreground text-sm">No documents found.</div>
                  ) : filteredDocuments.length === 0 ? (
                    <div className="py-2 text-muted-foreground text-sm">No documents match the selected filters.</div>
                  ) : (
                    <ul className="space-y-2">
                      {filteredDocuments.map((doc) => (
                        <li key={doc.id} className="border-b pb-2">
                          <div className="font-medium">{doc.file_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {doc.document_type && <span>Type: {doc.document_type} | </span>}
                            {doc.product_name && <span>Product: {doc.product_name} | </span>}
                            {doc.product_version && <span>Version: {doc.product_version} | </span>}
                            {doc.privacy_level && <span>Privacy: {doc.privacy_level} | </span>}
                            {doc.processed_at && <span>Processed: {new Date(doc.processed_at).toLocaleDateString()} </span>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 pb-2 flex items-center justify-between gap-2">
          <h3 className="text-sm font-medium text-muted-foreground">Recent Conversations</h3>
          <Button size="sm" variant="outline" onClick={onNewChat} className="flex items-center gap-1">
            <Plus className="h-4 w-4" />
            <span className="text-xs">New</span>
          </Button>
        </div>
        <div className="px-2 space-y-1">
          {conversationsLoading ? (
            <div className="px-1 py-2 text-sm text-muted-foreground">Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div className="px-1 py-2 text-sm text-muted-foreground">
              No conversations yet. Start a new chat to begin.
            </div>
          ) : (
            conversations.map((conversation) => {
              const latestTimestamp = conversation.updatedAt ?? conversation.createdAt
              const formattedDate = latestTimestamp ? new Date(latestTimestamp).toLocaleString() : ''
              return (
                <Button
                  key={conversation.id}
                  variant={currentConversationId === conversation.id ? "secondary" : "ghost"}
                  className="w-full justify-start text-left h-auto p-3"
                  onClick={() => onSelectConversation(conversation.id)}
                >
                  <div className="flex items-start gap-2 w-full">
                    <MessageCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="truncate text-sm">{conversation.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {formattedDate}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="ml-2 text-muted-foreground hover:text-destructive transition-colors"
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
                </Button>
              )
            })
          )}
        </div>
      </div>

      {/* Settings */}
      <div className="p-4 border-t">
        <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
          <DialogTrigger asChild>
            <Button variant="ghost" className="w-full justify-start">
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Settings</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <h4 className="text-sm font-medium">System Information</h4>
                <div className="text-sm text-muted-foreground space-y-1">
                  <div>Documents: {stats.documents}</div>
                  <div>Chunks: {stats.chunks}</div>
                  <div>RAG System: Production Ready ✅</div>
                  <div>Load Balancing: 4 Ollama Instances</div>
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Version Information</h4>
                <div className="text-sm text-muted-foreground space-y-1">
                  <div>Version: 1.0.0</div>
                  <div>Last Updated: September 24, 2025</div>
                  <div>Status: Docker Validated</div>
                </div>
              </div>
              <div className="pt-4 border-t">
                <Button 
                  variant="outline" 
                  onClick={() => setSettingsOpen(false)}
                  className="w-full"
                >
                  Close
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
