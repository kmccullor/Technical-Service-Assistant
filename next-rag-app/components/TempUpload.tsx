'use client'

import React, { useState, useCallback, useRef } from 'react'
import { Upload, File, X, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'

interface UploadedFile {
  sessionId: string
  fileName: string
  fileSize: number
  uploadTime: string
}

interface TempUploadProps {
  onFileUploaded?: (file: UploadedFile) => void
  onAnalysisResult?: (result: any) => void
}

const ALLOWED_EXTENSIONS = [
  '.txt', '.log', '.csv', '.json', '.sql', '.pdf', 
  '.xml', '.conf', '.config', '.ini', '.properties',
  '.out', '.err', '.trace', '.dump'
]

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export default function TempUpload({ onFileUploaded, onAnalysisResult }: TempUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analysisQuery, setAnalysisQuery] = useState('')
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): string | null => {
    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit`
    }

    // Check file extension
    const extension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      return `File type not supported. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
    }

    return null
  }

  const uploadFile = async (file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/temp-upload', {
        method: 'POST',
        body: formData
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
      onFileUploaded?.(uploadedFile)

    } catch (error) {
      console.error('Upload error:', error)
      setError(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  const handleFileSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return
    uploadFile(files[0])
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    handleFileSelect(e.dataTransfer.files)
  }, [])

  const analyzeDocument = async () => {
    if (!uploadedFile || !analysisQuery.trim()) return

    setIsAnalyzing(true)
    setError(null)

    try {
      const response = await fetch('/api/temp-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: uploadedFile.sessionId,
          query: analysisQuery.trim(),
          maxResults: 5
        })
      })

      const result = await response.json()

      if (response.ok) {
        setAnalysisResult(result)
        onAnalysisResult?.(result)
      } else {
        throw new Error(result.error || 'Analysis failed')
      }

    } catch (error) {
      console.error('Analysis error:', error)
      setError(error instanceof Error ? error.message : 'Analysis failed')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const clearFile = () => {
    setUploadedFile(null)
    setAnalysisQuery('')
    setAnalysisResult(null)
    setError(null)
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

  return (
    <div className="w-full max-w-2xl mx-auto p-6 space-y-6">
      {/* Upload Area */}
      {!uploadedFile && (
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            isDragOver
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept={ALLOWED_EXTENSIONS.join(',')}
            onChange={(e) => handleFileSelect(e.target.files)}
          />
          
          {isUploading ? (
            <div className="space-y-4">
              <Loader2 className="h-12 w-12 mx-auto text-blue-500 animate-spin" />
              <p className="text-gray-600">Uploading file...</p>
            </div>
          ) : (
            <div className="space-y-4">
              <Upload className="h-12 w-12 mx-auto text-gray-400" />
              <div>
                <p className="text-lg font-medium text-gray-900">
                  Upload Document for Analysis
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  Drag and drop a file here, or{' '}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="text-blue-500 hover:text-blue-600 font-medium"
                  >
                    browse to upload
                  </button>
                </p>
              </div>
              <div className="text-xs text-gray-400 space-y-1">
                <p>Supported: {ALLOWED_EXTENSIONS.slice(0, 6).join(', ')}...</p>
                <p>Max size: 10MB</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Uploaded File Info */}
      {uploadedFile && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <p className="font-medium text-green-900">{uploadedFile.fileName}</p>
                <p className="text-sm text-green-600">
                  {formatFileSize(uploadedFile.fileSize)} • Uploaded successfully
                </p>
              </div>
            </div>
            <button
              onClick={clearFile}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {/* Analysis Interface */}
      {uploadedFile && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Ask a question about the document:
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={analysisQuery}
                onChange={(e) => setAnalysisQuery(e.target.value)}
                placeholder="e.g., What errors are reported in this log?"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                onKeyDown={(e) => e.key === 'Enter' && analyzeDocument()}
              />
              <button
                onClick={analyzeDocument}
                disabled={!analysisQuery.trim() || isAnalyzing}
                className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {isAnalyzing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <File className="h-4 w-4" />
                )}
                <span>{isAnalyzing ? 'Analyzing...' : 'Analyze'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-900">Error</p>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysisResult && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div className="border-b pb-3">
            <h3 className="text-lg font-medium text-gray-900">Analysis Results</h3>
            <p className="text-sm text-gray-500">
              Confidence: {(analysisResult.confidence * 100).toFixed(1)}%
            </p>
          </div>
          
          <div className="prose prose-sm max-w-none">
            <div className="bg-gray-50 rounded p-4">
              <p className="font-medium text-gray-700 mb-2">Technical Analysis:</p>
              <div className="whitespace-pre-wrap text-gray-800">
                {analysisResult.response}
              </div>
            </div>
          </div>

          {analysisResult.results && analysisResult.results.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-medium text-gray-700">Relevant Sections:</h4>
              {analysisResult.results.map((result: any, index: number) => (
                <div key={index} className="bg-gray-50 rounded p-3 text-sm">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium text-gray-600">Section {result.rank}</span>
                    <span className="text-xs text-gray-500">
                      {(result.similarity * 100).toFixed(1)}% match
                    </span>
                  </div>
                  <p className="text-gray-700">{result.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}