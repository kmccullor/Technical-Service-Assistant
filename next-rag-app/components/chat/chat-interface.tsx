
'use client'
import React from 'react'

import { useState, useRef, useEffect } from 'react'
import { useAuth } from '@/src/context/AuthContext'
import { Copy } from 'lucide-react'
import * as Toast from '@radix-ui/react-toast'
import { MessageRenderer } from './message-renderer'
// Helper to format message for copying (plain text + optional metadata)
function formatMessageForCopy(message: Message): string {
  let text = message.content
  if (message.citations && message.citations.length > 0) {
    text += '\n\nSources:'
    for (const c of message.citations) {
      text += `\n- ${c.title} (${c.source})${c.score ? ` [${(c.score * 100).toFixed(0)}% match]` : ''}`
    }
  }
  text += `\n\nTimestamp: ${message.timestamp.toLocaleString()}`
  return text
}
// Copy to clipboard with fallback
async function copyToClipboard(text: string) {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text)
  } else {
    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
}
import { Send, Loader2, FileText, Search, Globe, Paperclip, X, Upload, CheckCircle, AlertCircle, Maximize2, Minimize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

interface Citation {
  id: string
  title: string
  content: string
  source: string
  score?: number
  page?: number
}

interface UploadedFile {
  sessionId: string
  fileName: string
  fileSize: number
  uploadTime: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  searchType?: 'documents' | 'web' | 'hybrid' | 'temp-doc'
  uploadedFile?: UploadedFile
  timestamp: Date
}

interface ChatInterfaceProps {
  conversationId?: number
  onConversationCreated?: (conversationId: number) => void
  onConversationActivity?: (conversationId: number) => void
}

const ALLOWED_EXTENSIONS = [
  '.txt', '.log', '.csv', '.json', '.sql', '.pdf',
  '.xml', '.conf', '.config', '.ini', '.properties',
  '.out', '.err', '.trace', '.dump', '.png', '.jpg',
  '.jpeg', '.gif', '.bmp', '.tiff', '.webp'
]
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export function ChatInterface({ conversationId, onConversationCreated, onConversationActivity }: ChatInterfaceProps) {
  const { accessToken } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [inputExpanded, setInputExpanded] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const isInitialScrollRef = useRef(true)

  const scrollToBottom = (behavior: ScrollBehavior = 'auto') => {
    const el = messagesContainerRef.current
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior })
    }
  }

  useEffect(() => {
    scrollToBottom(isInitialScrollRef.current ? 'auto' : 'smooth')
    isInitialScrollRef.current = false
  }, [messages])

  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)

  // Handle conversation changes - load history for existing conversations
  useEffect(() => {
    let cancelled = false

    const loadHistory = async (id: number) => {
      if (!accessToken) {
        setHistoryError('Authentication required to load conversation.')
        setMessages([])
        return
      }
      try {
        setHistoryLoading(true)
        setHistoryError(null)
        const response = await fetch(`/api/conversations/${id}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          cache: 'no-store',
        })
        if (!response.ok) {
          if (response.status === 404) {
            setHistoryError('Conversation not found.')
            setMessages([])
            return
          }
          const detail = await response.text().catch(() => '')
          throw new Error(detail || `Failed to load conversation (status ${response.status})`)
        }
        const data = await response.json()
        if (cancelled) return
        const mapped: Message[] = Array.isArray(data?.messages)
          ? data.messages.map((msg: any) => ({
              id: String(msg.id),
              role: msg.role === 'assistant' ? 'assistant' : 'user',
              content: msg.content ?? '',
              citations: Array.isArray(msg.citations) ? msg.citations : undefined,
              searchType: msg.searchType ?? msg.method,
              timestamp: new Date(msg.createdAt ?? msg.created_at ?? new Date().toISOString()),
            }))
          : []
        setMessages(mapped)
        setUploadedFile(null)
        setUploadError(null)
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load conversation history:', error)
          setHistoryError('Unable to load conversation history.')
          setMessages([])
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false)
        }
      }
    }

    if (conversationId === undefined) {
      setMessages([])
      setInput('')
      setUploadedFile(null)
      setUploadError(null)
      setHistoryError(null)
      setHistoryLoading(false)
    } else {
      loadHistory(conversationId)
    }

    isInitialScrollRef.current = true

    return () => {
      cancelled = true
    }
  }, [conversationId, accessToken])

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit`
    }

    const extension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      return `File type not supported. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
    }

    return null
  }

  const handleFileUpload = async (file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      setUploadError(validationError)
      return
    }

    setIsUploading(true)
    setUploadError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/temp-upload', {
        method: 'POST',
        body: formData,
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined
      })

      const result = await response.json()

      if (!result.success) {
        throw new Error(result.error || 'Upload failed')
      }

      const uploadedFile: UploadedFile = {
        sessionId: result.sessionId,
        fileName: result.fileName,
        fileSize: result.fileSize,
        uploadTime: new Date().toISOString()
      }

      setUploadedFile(uploadedFile)

      // Add a system message about the upload
      const systemMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `✅ **File uploaded successfully:** ${file.name} (${formatFileSize(file.size)})\n\nYou can now ask questions about this document. I'll analyze its content to provide specific insights and troubleshooting assistance.`,
        searchType: 'temp-doc',
        uploadedFile: uploadedFile,
        timestamp: new Date()
      }

      setMessages(prev => [...prev, systemMessage])

    } catch (error) {
      console.error('Upload error:', error)
      setUploadError(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (files && files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const clearUploadedFile = () => {
    setUploadedFile(null)
    setUploadError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  // Drag and drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set isDragOver to false if we're leaving the chat container
    if (!chatContainerRef.current?.contains(e.relatedTarget as Node)) {
      setIsDragOver(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  // Toast state for copy feedback
  const [toastOpen, setToastOpen] = useState(false)
  const [toastMsg, setToastMsg] = useState('')

  // Add global drag event listeners to detect drag enter/leave
  useEffect(() => {
    const handleGlobalDragEnter = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes('Files')) {
        setIsDragOver(true)
      }
    }

    const handleGlobalDragLeave = (e: DragEvent) => {
      // Only hide drag overlay if we're leaving the window
      if (e.clientX === 0 && e.clientY === 0) {
        setIsDragOver(false)
      }
    }

    document.addEventListener('dragenter', handleGlobalDragEnter)
    document.addEventListener('dragleave', handleGlobalDragLeave)

    return () => {
      document.removeEventListener('dragenter', handleGlobalDragEnter)
      document.removeEventListener('dragleave', handleGlobalDragLeave)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const rawInput = input.trim()
    if (!rawInput || isLoading) return
    if (!accessToken) {
      setToastMsg('Please sign in to chat.')
      setToastOpen(true)
      return
    }

    const commandMatch = rawInput.match(/^\/(new|update|close)\s+case\s+(.+)$/i)
    let displayContent = rawInput
    let outboundContent = rawInput

    if (commandMatch) {
      const action = commandMatch[1].toLowerCase()
      const caseNumber = commandMatch[2].trim()
      if (!caseNumber) {
        setToastMsg('Please provide a case number, e.g. /new case 01125052')
        setToastOpen(true)
        return
      }

      if (action === 'new') {
        displayContent = `📄 Initiating Salesforce case ${caseNumber}`
        outboundContent = `You are assisting with Salesforce case ${caseNumber}. Using the conversation context, define the case for analysis and recommendation by providing:\n- A concise case overview with important facts known so far.\n- Immediate diagnostic or triage steps to perform.\n- Clarifying questions that should be asked of the customer.\n- Recommended next actions for engineering/support teams.\nReturn the response with headings: Case Overview, Immediate Actions, Clarifying Questions, Recommended Next Steps.`
      } else if (action === 'update') {
        displayContent = `🛠️ Updating Salesforce case ${caseNumber}`
        outboundContent = `You are providing an update on Salesforce case ${caseNumber}. Review the conversation context and produce:\n- The current status/progress of the case.\n- Outstanding issues or blockers.\n- Recommended next steps for the support engineer.\n- Suggested customer communication points.\nReturn the response with headings: Case Status, Outstanding Items, Recommended Actions, Customer Communication.`
      } else if (action === 'close') {
        displayContent = `✅ Closing Salesforce case ${caseNumber}`
        outboundContent = `You are preparing to close Salesforce case ${caseNumber}. Based on the conversation context, provide:\n- A brief incident summary.\n- Actions taken and resolutions applied.\n- Verification steps or final checks completed/needed.\n- Final closing comments for the customer.\nReturn the response with headings: Summary, Actions Taken, Verification, Closing Comments.`
      }
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: displayContent,
      uploadedFile: uploadedFile || undefined,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    const currentInput = outboundContent
    setInput('')
    setIsLoading(true)

    try {
      // If there's an uploaded file, analyze it using temp-analyze endpoint
      if (uploadedFile) {
        const response = await fetch('/api/temp-analyze', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
          },
          body: JSON.stringify({
            sessionId: uploadedFile.sessionId,
            query: currentInput,
            maxResults: 5
          }),
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const result = await response.json()

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.response,
          citations: result.results?.map((r: any, idx: number) => ({
            id: `temp-${idx}`,
            title: `Section ${r.rank}`,
            content: r.content,
            source: uploadedFile.fileName,
            score: r.similarity
          })),
          searchType: 'temp-doc',
          timestamp: new Date()
        }

        setMessages(prev => [...prev, assistantMessage])
        return
      }

      // Regular chat without uploaded file - use streaming RAG endpoint
      const response = await fetch(`${process.env.NEXT_PUBLIC_RERANKER_BASE_URL || 'http://localhost:8008'}/api/rag-chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: currentInput,
          use_context: true,
          max_context_chunks: 5,
          stream: true,
          temperature: 0.2,
          max_tokens: 500,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      let assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date()
      }
      let resolvedConversationId: number | undefined = conversationId

      setMessages(prev => [...prev, assistantMessage])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = new TextDecoder().decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'token') {
                // Handle streaming tokens from the backend
                setMessages(prev => prev.map(m =>
                  m.id === assistantMessage.id
                    ? { ...m, content: m.content + data.token }
                    : m
                ))
              } else if (data.type === 'sources') {
                // Handle sources/citations
                setMessages(prev => prev.map(m =>
                  m.id === assistantMessage.id
                    ? { ...m, citations: data.sources, searchType: data.method }
                    : m
                ))
              } else if (data.type === 'conversation_id') {
                if (typeof data.conversationId === 'number') {
                  resolvedConversationId = data.conversationId
                  if (conversationId === undefined) {
                    onConversationCreated?.(data.conversationId)
                  }
                }
              } else if (data.type === 'done') {
                // Streaming completed
                console.log('Streaming completed')
              } else if (data.type === 'error') {
                console.error('Streaming error:', data.error)
              }
            } catch (e) {
              // Ignore malformed JSON
              console.warn('Failed to parse streaming data:', line)
            }
          }
        }
      }

      if (resolvedConversationId !== undefined) {
        onConversationActivity?.(resolvedConversationId)
      }
    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const getSearchIcon = (searchType?: string) => {
    switch (searchType) {
      case 'documents': return <FileText className="h-3 w-3" />
      case 'web': return <Globe className="h-3 w-3" />
      case 'hybrid': return <Search className="h-3 w-3" />
      case 'temp-doc': return <Upload className="h-3 w-3" />
      default: return <Search className="h-3 w-3" />
    }
  }

  const getSearchLabel = (searchType?: string) => {
    switch (searchType) {
      case 'documents': return 'Document Search'
      case 'web': return 'Web Search'
      case 'hybrid': return 'Hybrid Search'
      case 'temp-doc': return 'Uploaded Document'
      default: return 'Search'
    }
  }

  return (
    <div
      ref={chatContainerRef}
      className="flex h-full min-h-0 flex-col relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag Overlay */}
      {isDragOver && (
        <div className="absolute inset-0 z-50 bg-blue-500/10 backdrop-blur-sm flex items-center justify-center border-2 border-dashed border-blue-500">
          <div className="text-center p-8 bg-white/90 rounded-lg shadow-lg">
            <Upload className="h-12 w-12 mx-auto text-blue-500 mb-4" />
            <h3 className="text-xl font-semibold text-blue-900 mb-2">Drop file to analyze</h3>
            <p className="text-blue-700">
              Supports logs, configs, PDFs, images, and more
            </p>
            <p className="text-sm text-blue-600 mt-2">
              AI will analyze your document with Technical Service Assistant expertise
            </p>
          </div>
        </div>
      )}

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 pb-32 space-y-4">
        {historyLoading && messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            <Loader2 className="h-10 w-10 mx-auto mb-4 animate-spin" />
            <p>Loading conversation...</p>
          </div>
        ) : historyError && messages.length === 0 ? (
          <div className="text-center text-red-500 py-8">
            <AlertCircle className="h-10 w-10 mx-auto mb-4" />
            <p>{historyError}</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <h3 className="text-lg font-medium mb-2">Start a conversation</h3>
            <p>Ask questions about your documents or any topic.</p>
          </div>
        ) : null}

        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
             <div className={`max-w-[80%] ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'} rounded-lg p-4 relative`}>
               <MessageRenderer content={message.content} />
              {/* Copy button for assistant messages */}
              {message.role === 'assistant' && (
                <button
                  className="absolute top-2 right-2 p-1 rounded hover:bg-accent focus:outline-none focus:ring"
                  title="Copy response"
                  aria-label="Copy response"
                  data-testid="copy-btn"
                  onClick={async () => {
                    try {
                      await copyToClipboard(formatMessageForCopy(message))
                      setToastMsg('Copied to clipboard!')
                      setToastOpen(true)
                    } catch (e) {
                      setToastMsg('Copy failed')
                      setToastOpen(true)
                    }
                  }}
                >
                  <Copy className="h-4 w-4 text-muted-foreground" />
                </button>
              )}
              {message.citations && message.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border/20">
                  <div className="flex items-center gap-2 mb-2">
                    {getSearchIcon(message.searchType)}
                    <span className="text-xs font-medium">{getSearchLabel(message.searchType)}</span>
                    <Badge variant="secondary" className="text-xs">
                      {message.citations.length} source{message.citations.length !== 1 ? 's' : ''}
                    </Badge>
                  </div>
                  <Collapsible>
                    <CollapsibleTrigger className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                      Show sources ↓
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-2 space-y-2">
                      {message.citations.map((citation, idx) => (
                        <Card key={idx} className="text-xs">
                          <CardContent className="p-3">
                            <div className="font-medium mb-1">{citation.title}</div>
                            <div className="text-muted-foreground mb-2 line-clamp-2">
                              {citation.content}
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-muted-foreground">{citation.source}</span>
                              {citation.score && (
                                <Badge variant="outline">
                                  {(citation.score * 100).toFixed(0)}% match
                                </Badge>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>
                </div>
              )}
            </div>
          </div>
        ))}
        {historyLoading && messages.length > 0 && (
          <div className="text-center text-xs text-muted-foreground">Updating conversation…</div>
        )}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg p-4">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="sticky bottom-0 z-10 border-t bg-background p-4">
        {/* File Upload Area */}
        {uploadedFile && (
          <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <div>
                <span className="font-medium text-green-900">{uploadedFile.fileName}</span>
                <span className="text-sm text-green-600 ml-2">({formatFileSize(uploadedFile.fileSize)})</span>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearUploadedFile}
              className="text-green-700 hover:text-green-800"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {uploadError && (
          <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-red-500 mt-0.5" />
            <div>
              <div className="font-medium text-red-900">Upload Error</div>
              <div className="text-sm text-red-600">{uploadError}</div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setUploadError(null)}
              className="text-red-700 hover:text-red-800 ml-auto"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Press Enter to send, Shift+Enter for a new line.</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setInputExpanded(prev => !prev)}
                className="text-muted-foreground hover:text-foreground"
                title={inputExpanded ? 'Collapse input' : 'Expand input'}
              >
                {inputExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          <div className="relative">
            <Textarea
              value={input}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setInput(e.target.value)}
              placeholder={uploadedFile ?
                (uploadedFile.fileName.match(/\.(png|jpg|jpeg|gif|bmp|tiff|webp)$/i) ?
                  "Describe what you see in the image or ask questions about it..." :
                  "Ask questions about the uploaded document...") :
                "Ask a question about your documents..."}
              className={`w-full pr-12 resize-y ${inputExpanded ? 'min-h-[180px]' : 'min-h-[80px]'} max-h-[320px]`}
              onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e as any)
                }
              }}
            />
            <div className="absolute right-3 bottom-3 flex items-center gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept={ALLOWED_EXTENSIONS.join(',')}
                className="hidden"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="h-7 w-7"
                title="Upload document for analysis"
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Paperclip className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="text-xs text-muted-foreground">
              {!uploadedFile && '💡 Tip: Click the clip icon or drag & drop files to upload logs, configs, images, or other documents.'}
            </div>
            <Button type="submit" disabled={!input.trim() || isLoading}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Send className="h-4 w-4 mr-1" /> Send</>}
            </Button>
          </div>
        </form>

        {!uploadedFile && (
          <div className="mt-2 text-xs text-muted-foreground">
            Need to describe a longer issue? Expand the input or attach files for deeper analysis.
          </div>
        )}
      </div>
      {/* Toast notification for copy feedback */}
      <Toast.Provider swipeDirection="right">
        <Toast.Root open={toastOpen} onOpenChange={setToastOpen} duration={2000} className="bg-black text-white px-4 py-2 rounded shadow-lg">
          <Toast.Title>{toastMsg}</Toast.Title>
        </Toast.Root>
        <Toast.Viewport className="fixed bottom-4 right-4 z-50" />
      </Toast.Provider>
    </div>
  )
}
