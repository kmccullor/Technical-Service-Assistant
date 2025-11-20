'use client'

import React, { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from '@/components/ui/dialog-client'
import { ChatMessage } from '@/components/chat/types'

interface AdminActionPanelProps {
  conversationId?: number
  lastAssistantMessage?: ChatMessage | null
  customPrompt: string
  onPromptChange: (next: string) => void
  onRegenerate?: () => void
}

const TOOL_DEFINITIONS = [
  { id: 'admin-users', label: 'Admin Users', endpoint: '/api/admin/users?limit=3' },
  { id: 'auth-health', label: 'Auth Health', endpoint: '/api/auth/health' },
  { id: 'cache-stats', label: 'Cache Stats', endpoint: '/api/cache-stats' },
]

export function AdminActionPanel({ conversationId, lastAssistantMessage, customPrompt, onPromptChange, onRegenerate }: AdminActionPanelProps) {
  const [draftPrompt, setDraftPrompt] = useState(customPrompt)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [toolResult, setToolResult] = useState<string | null>(null)
  const [toolLoading, setToolLoading] = useState(false)

  useEffect(() => {
    setDraftPrompt(customPrompt)
  }, [customPrompt])

  const handleExport = () => {
    if (!lastAssistantMessage) {
      setStatusMessage('No response available to export yet.')
      return
    }
    const lines = [
      `# Exported Response ${new Date().toISOString()}`,
      `Conversation: ${conversationId ?? 'new'}`,
      '',
      lastAssistantMessage.content,
    ]
    if (lastAssistantMessage.citations && lastAssistantMessage.citations.length > 0) {
      lines.push('', '## Citations')
      for (const citation of lastAssistantMessage.citations) {
        lines.push(`- ${citation.title} (${citation.source})`)
      }
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `tsa-response-${conversationId ?? 'draft'}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    setStatusMessage('Answer exported locally for audit.')
  }

  const handleToolClick = async (endpoint: string) => {
    setToolLoading(true)
    setToolResult(null)
    try {
      const response = await fetch(endpoint)
      const payload = await response.json().catch(() => ({ status: response.status }))
      setToolResult(JSON.stringify(payload).slice(0, 240))
    } catch (error) {
      setToolResult(`Tool failed: ${(error as Error).message}`)
    } finally {
      setToolLoading(false)
    }
  }

  return (
    <Card className="space-y-4 mb-4">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Admin Actions</CardTitle>
        <CardDescription className="text-xs">Regenerate insights, tweak prompts, or export a finalized answer.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => {
            setStatusMessage('Regeneration requested. Re-querying latest insight...')
            onRegenerate?.()
          }}>
            Regenerate
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">Tweak prompt</Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Prompt tuning</DialogTitle>
                <DialogDescription>Adjust the Salesforce research framing that gets sent to the chat API.</DialogDescription>
              </DialogHeader>
              <Textarea
                value={draftPrompt}
                onChange={(event) => setDraftPrompt(event.target.value)}
                className="h-36"
                placeholder="Describe how the assistant should approach Sensus AMI cases..."
              />
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => setDraftPrompt(customPrompt)}>Reset</Button>
                <Button variant="secondary" size="sm" onClick={() => {
                  onPromptChange(draftPrompt)
                  setStatusMessage('Prompt updated — new queries adopt this wording.')
                }}>Save</Button>
              </div>
            </DialogContent>
          </Dialog>
          <Button variant="ghost" size="sm" onClick={handleExport}>Export answer</Button>
        </div>
        <div className="text-xs text-muted-foreground">Tools</div>
        <div className="flex flex-wrap gap-2">
          {TOOL_DEFINITIONS.map(tool => (
            <Button
              key={tool.id}
              variant="outline"
              size="sm"
              onClick={() => handleToolClick(tool.endpoint)}
            >
              {tool.label}
            </Button>
          ))}
        </div>
        {toolLoading && <p className="text-xs text-muted-foreground">Fetching selected tool…</p>}
        {toolResult && (
          <pre className="text-xs max-h-24 overflow-auto rounded-md bg-muted/50 p-2">{toolResult}</pre>
        )}
        {statusMessage && <p className="text-xs text-muted-foreground">{statusMessage}</p>}
      </CardContent>
    </Card>
  )
}
