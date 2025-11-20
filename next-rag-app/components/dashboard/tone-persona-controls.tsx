'use client'

import React from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

const PERSONA_OPTIONS: Array<{ id: 'friendly' | 'formal'; label: string; caption: string }> = [
  { id: 'friendly', label: 'Friendly', caption: 'Warm, conversational, helps Salesforce engineers talk to customers.' },
  { id: 'formal', label: 'Formal', caption: 'Precise, compliant, fits executive summaries.' },
]

const TONE_OPTIONS: Array<{ id: 'concise' | 'verbose'; label: string; caption: string }> = [
  { id: 'concise', label: 'Concise', caption: 'Bullet-ready answers, ideal for quick status updates.' },
  { id: 'verbose', label: 'Verbose', caption: 'Deep dives with explicit reasoning for complex Sensus AMI cases.' },
]

interface TonePersonaControlsProps {
  persona: 'friendly' | 'formal'
  tone: 'concise' | 'verbose'
  onPersonaChange: (value: 'friendly' | 'formal') => void
  onToneChange: (value: 'concise' | 'verbose') => void
}

export function TonePersonaControls({ persona, tone, onPersonaChange, onToneChange }: TonePersonaControlsProps) {
  const samplePrompt = `You are a ${persona} technical analyst answering Salesforce cases about Sensus AMI products. Keep the delivery ${tone === 'concise' ? 'brief and actionable' : 'detailed with context'}. Reference the Postgres + pgvector knowledge base.`

  return (
    <Card className="space-y-4">
      <CardHeader className="space-y-1">
        <CardTitle className="text-lg">Tone & Persona</CardTitle>
        <CardDescription>Choose how the assistant communicates and preview a matching prompt.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Persona</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {PERSONA_OPTIONS.map(option => (
              <Button
                key={option.id}
                size="sm"
                variant={persona === option.id ? 'secondary' : 'ghost'}
                onClick={() => onPersonaChange(option.id)}
                className="text-xs"
              >
                {option.label}
              </Button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">{PERSONA_OPTIONS.find(p => p.id === persona)?.caption}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Tone</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {TONE_OPTIONS.map(option => (
              <Button
                key={option.id}
                size="sm"
                variant={tone === option.id ? 'secondary' : 'ghost'}
                onClick={() => onToneChange(option.id)}
                className="text-xs"
              >
                {option.label}
              </Button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">{TONE_OPTIONS.find(t => t.id === tone)?.caption}</p>
        </div>
      </CardContent>
      <CardContent className="bg-muted/50 rounded-xl">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Sample prompt</p>
        <pre className="text-sm mt-2 whitespace-pre-line">{samplePrompt}</pre>
      </CardContent>
    </Card>
  )
}
