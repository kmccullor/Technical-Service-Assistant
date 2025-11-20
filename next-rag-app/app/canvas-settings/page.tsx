'use client'

import React, { useState } from 'react'
import { TonePersonaControls } from '@/components/dashboard/tone-persona-controls'

export default function CanvasSettingsPage() {
  const [persona, setPersona] = useState<'friendly' | 'formal'>('friendly')
  const [tone, setTone] = useState<'concise' | 'verbose'>('concise')

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-6 py-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Canvas Settings</h1>
        <p className="text-sm text-muted-foreground">
          Adjust tone, persona, and other chat behaviors. These defaults apply to new conversations and help the
          assistant align with your preferred voice.
        </p>
      </div>
      <TonePersonaControls persona={persona} tone={tone} onPersonaChange={setPersona} onToneChange={setTone} />
    </div>
  )
}
