'use client'

import React, { useMemo, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Pin, Edit3, X } from 'lucide-react'

interface ContextSource {
  id: string
  title: string
  summary: string
  source: string
  url?: string
}

interface MemoryEntry {
  id: string
  title: string
  snippet: string
  timestamp: string
}

interface ContextDrawerProps {
  isOpen: boolean
  onClose: () => void
  systemPrompts: string[]
  sources: ContextSource[]
  memoryEntries: MemoryEntry[]
}

export function ContextDrawer({ isOpen, onClose, systemPrompts, sources, memoryEntries }: ContextDrawerProps) {
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(new Set())

  const enhancedSources = useMemo(() => {
    return sources.map(source => ({
      ...source,
      label: source.source.includes('Sensus') ? 'Sensus AMI KB' : source.source,
    }))
  }, [sources])

  const togglePin = (id: string) => {
    setPinnedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (!isOpen) return null

  return (
    <div className="flex h-full w-96 max-h-[calc(100vh-96px)] flex-col rounded-[40px] border border-border/60 bg-background/95 shadow-2xl">
      <div className="flex items-center justify-between rounded-t-[40px] border-b border-border/40 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Context Drawer</p>
          <p className="text-lg font-semibold">System Prompts & Sources</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto space-y-4 p-5">
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">System prompts</p>
            <Badge variant="outline">Key guardrails</Badge>
          </div>
          <div className="space-y-2">
            {systemPrompts.map((prompt, idx) => (
              <Card key={`prompt-${idx}`} className="bg-muted/50" aria-label="system prompt">
                <div className="space-y-1">
                  <p className="text-xs uppercase text-muted-foreground">Prompt #{idx + 1}</p>
                  <p className="text-sm">{prompt}</p>
                </div>
              </Card>
            ))}
          </div>
        </section>
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Memory & pinned turns</p>
            <Badge variant="outline">{pinnedIds.size} pinned</Badge>
          </div>
          <div className="space-y-2">
            {memoryEntries.map(entry => (
              <Card key={entry.id} className="border-primary/30">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold">{entry.title}</p>
                    <p className="text-xs text-muted-foreground">{entry.timestamp}</p>
                    <p className="text-sm mt-1 line-clamp-3">{entry.snippet}</p>
                  </div>
                  <div className="flex flex-col gap-1">
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={() => togglePin(entry.id)}
                      title={pinnedIds.has(entry.id) ? 'Unpin turn' : 'Pin turn'}
                    >
                      <Pin className={`h-4 w-4 ${pinnedIds.has(entry.id) ? 'text-primary' : ''}`} />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" title="Edit turn">
                      <Edit3 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Sources</p>
            <Badge variant="secondary">PGVector</Badge>
          </div>
          <div className="space-y-2">
            {enhancedSources.map(source => (
              <Card key={source.id} className="bg-muted/50">
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-sm">{source.title}</p>
                    <Badge variant="outline" className="text-[10px]">{source.label}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{source.summary}</p>
                  <p className="text-xs text-muted-foreground">{source.source}</p>
                  {source.url && (
                    <a href={source.url} className="text-xs text-primary underline" target="_blank" rel="noreferrer">
                      Open reference
                    </a>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
