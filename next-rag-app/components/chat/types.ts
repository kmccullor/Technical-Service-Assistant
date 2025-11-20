export type SearchType = 'documents' | 'web' | 'hybrid' | 'temp-doc'

export interface Citation {
  id: string
  title: string
  content: string
  source: string
  score?: number
  page?: number
}

export interface UploadedFile {
  sessionId: string
  fileName: string
  fileSize: number
  uploadTime: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  searchType?: SearchType
  uploadedFile?: UploadedFile
  timestamp: Date
}
