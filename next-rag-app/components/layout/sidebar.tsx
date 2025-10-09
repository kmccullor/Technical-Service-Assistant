
'use client'
import React from 'react'

import { useState, useEffect } from 'react'
import { useAuth } from '@/src/context/AuthContext'
import { Plus, MessageCircle, FileText, Search, Settings, X, Upload, Shield } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

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
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [stats, setStats] = useState({ documents: 0, chunks: 0 })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { accessToken, user } = useAuth()

  useEffect(() => {
    fetchStats()
    fetchConversations()
  }, [accessToken])

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/stats', { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined })
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  const fetchConversations = async () => {
    try {
      const response = await fetch('/api/conversations', { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined })
      if (response.ok) {
        const data = await response.json()
        setConversations(data)
      }
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    }
  }

  return (
    <div className="w-64 bg-muted/30 border-r flex flex-col">
      {/* Header */}
      <div className="p-4 border-b">
        <h1 className="text-lg font-semibold flex items-center gap-2">
          <Search className="h-5 w-5" />
          Technical Services Assistant
        </h1>
      </div>

      {/* New Chat */}
      <div className="p-4 space-y-2">
        <Button onClick={onNewChat} className="w-full" variant="outline">
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
        <Link href="/temp-analysis" className="block">
          <Button variant="ghost" className="w-full justify-start">
            <Upload className="h-4 w-4 mr-2" />
            Document Analysis
          </Button>
        </Link>
        <Link href="/data-dictionary" className="block">
          <Button variant="ghost" className="w-full justify-start">
            <FileText className="h-4 w-4 mr-2" />
            Data Dictionary
          </Button>
        </Link>
        {user?.role_name === 'admin' && (
          <Link href="/admin" className="block">
            <Button variant="ghost" className="w-full justify-start text-amber-600 dark:text-amber-400">
              <Shield className="h-4 w-4 mr-2" />
              Admin
            </Button>
          </Link>
        )}
      </div>

      {/* Stats */}
      <div className="px-4 pb-4">
        <Card className="p-3">
          <div className="text-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <FileText className="h-3 w-3" />
                Documents
              </span>
              <span className="font-mono">{stats.documents}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Search className="h-3 w-3" />
                Chunks
              </span>
              <span className="font-mono">{stats.chunks}</span>
            </div>
          </div>
        </Card>
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