
'use client'
import React from 'react'

import { useState, useEffect } from 'react'
import { useAuth } from '@/src/context/AuthContext'
import { Plus, MessageCircle, FileText, Search, Settings, X, Upload, Shield } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from '@/components/ui/dialog'

interface Conversation {
  id: number
  title: string
  createdAt: Date
}

interface SidebarProps {
  onNewChat: () => void
  onSelectConversation: (id: number) => void
  currentConversationId?: number
}

export function Sidebar({ onNewChat, onSelectConversation, currentConversationId }: SidebarProps) {
  // Stub implementations for missing functions
  async function fetchStats() {
    // TODO: Replace with real API call
    setStats({ documents: 42, chunks: 1234 })
  }

  async function fetchConversations() {
    // TODO: Replace with real API call
    setConversations([
      { id: 1, title: 'Welcome Conversation', createdAt: new Date() },
      { id: 2, title: 'System Demo', createdAt: new Date() },
    ])
  }
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [stats, setStats] = useState({ documents: 0, chunks: 0 })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [documentsOpen, setDocumentsOpen] = useState(false)
  const [documents, setDocuments] = useState<any[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [documentsError, setDocumentsError] = useState<string | null>(null)
  const { accessToken, user } = useAuth()

  useEffect(() => {
    fetchStats()
    fetchConversations()
  }, [accessToken])

  useEffect(() => {
    if (documentsOpen) {
      setDocumentsLoading(true)
      setDocumentsError(null)
      fetch('/api/documents')
        .then((res) => {
          if (!res.ok) throw new Error('Failed to fetch documents')
          return res.json()
        })
        .then((data) => {
          setDocuments(data.documents || [])
          setDocumentsLoading(false)
        })
        .catch((err) => {
          setDocumentsError(err.message || 'Unknown error')
          setDocumentsLoading(false)
        })
    }
  }, [documentsOpen])

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
            ) : documents.length === 0 ? (
              <div className="py-2 text-muted-foreground text-sm">No documents found.</div>
            ) : (
              <ul className="py-2 space-y-2">
                {documents.map((doc) => (
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
          </DialogContent>
        </Dialog>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 pb-2">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Recent Conversations</h3>
        </div>
        <div className="px-2 space-y-1">
          {conversations.map((conversation) => (
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
                    {new Date(conversation.createdAt).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </Button>
          ))}
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