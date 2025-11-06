'use client'

import React from 'react'
import { CodeBlock } from '@/components/ui/code-block'

interface MessageRendererProps {
  content: string
  className?: string
}

export function MessageRenderer({ content, className = '' }: MessageRendererProps) {
  // Parse content for code blocks marked with ```
  const parseContent = (text: string) => {
    const parts: Array<{ type: 'text' | 'code', content: string, language?: string }> = []
    const codeBlockRegex = /```(\w+)?\n?([\s\S]*?)```/g

    let lastIndex = 0
    let match

    while ((match = codeBlockRegex.exec(text)) !== null) {
      // Add text before the code block
      if (match.index > lastIndex) {
        const textContent = text.slice(lastIndex, match.index)
        if (textContent.trim()) {
          parts.push({ type: 'text', content: textContent })
        }
      }

      // Add the code block
      const language = match[1]
      const code = match[2].trim()
      parts.push({ type: 'code', content: code, language })

      lastIndex = match.index + match[0].length
    }

    // Add remaining text
    if (lastIndex < text.length) {
      const remainingText = text.slice(lastIndex)
      if (remainingText.trim()) {
        parts.push({ type: 'text', content: remainingText })
      }
    }

    // If no code blocks found, treat as plain text
    if (parts.length === 0) {
      parts.push({ type: 'text', content: text })
    }

    return parts
  }

  const parts = parseContent(content)

  return (
    <div className={`whitespace-pre-wrap break-words ${className}`}>
      {parts.map((part, index) => {
        if (part.type === 'code') {
          return (
            <CodeBlock
              key={index}
              code={part.content}
              language={part.language}
              className="my-2"
            />
          )
        } else {
          return (
            <span key={index}>
              {part.content}
            </span>
          )
        }
      })}
    </div>
  )
}