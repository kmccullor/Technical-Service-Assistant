'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { deleteDocument, downloadDocument, listDocuments, type DocumentInfo } from '@/lib/admin'
import { useAuth } from '@/src/context/AuthContext'
import { Button } from '@/components/ui/button'

function formatBytes(bytes?: number | null): string {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / Math.pow(1024, idx)
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[idx]}`
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString()
}

export default function DocsPage() {
  const { accessToken, user, loading } = useAuth()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [totalCount, setTotalCount] = useState(0)
  const [offset, setOffset] = useState(0)
  const PAGE_SIZE = 50
  const [sortBy, setSortBy] = useState<'title' | 'type' | 'product' | 'chunks' | 'size' | 'processed'>('processed')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  const fetchDocuments = async () => {
    if (!accessToken) {
      setDocuments([])
      setDocsLoading(false)
      return
    }
    try {
      setDocsLoading(true)
      const response = await listDocuments({
        accessToken,
        limit: PAGE_SIZE,
        offset,
        search_term: searchTerm.trim() || undefined,
        sort_by: 'processed_at',
        sort_order: 'desc',
      })
      setDocuments(response.documents ?? [])
      setTotalCount(response.total_count ?? 0)
      setSelectedIds(new Set())
      setError(null)
    } catch (err: any) {
      console.error('[Docs] failed to load documents', err)
      setError(err?.message || 'Unable to load documents')
      setDocuments([])
    } finally {
      setDocsLoading(false)
    }
  }

  useEffect(() => {
    if (!accessToken) {
      setDocsLoading(false)
      return
    }
    fetchDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, offset, searchTerm])

  const stats = useMemo(() => {
    const totalSize = documents.reduce((sum, doc) => sum + (doc.file_size ?? 0), 0)
    return {
      count: totalCount,
      totalSize: formatBytes(totalSize),
    }
  }, [documents, totalCount])

  const isAdmin = user?.role_name?.toLowerCase() === 'admin'
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [downloading, setDownloading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const visibleDocuments = useMemo(() => {
    const sorted = [...documents].sort((a, b) => {
      const dir = sortDirection === 'asc' ? 1 : -1
      switch (sortBy) {
        case 'title':
          return dir * (a.title || a.file_name || '').localeCompare(b.title || b.file_name || '')
        case 'type':
          return dir * (a.document_type || '').localeCompare(b.document_type || '')
        case 'product': {
          const aProd = `${a.product_name || ''}${a.product_version || ''}`
          const bProd = `${b.product_name || ''}${b.product_version || ''}`
          return dir * aProd.localeCompare(bProd)
        }
        case 'chunks':
          return dir * ((a.chunk_count || 0) - (b.chunk_count || 0))
        case 'size':
          return dir * ((a.file_size || 0) - (b.file_size || 0))
        case 'processed':
        default: {
          const aDate = new Date(a.processed_at || a.created_at || 0).getTime()
          const bDate = new Date(b.processed_at || b.created_at || 0).getTime()
          return dir * (aDate - bDate)
        }
      }
    })

    return sorted
  }, [documents, sortBy, sortDirection])

  const selectedDocuments = useMemo(() => {
    if (selectedIds.size === 0) return []
    return documents.filter((doc) => selectedIds.has(doc.id))
  }, [documents, selectedIds])

  const toggleDocumentSelection = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === visibleDocuments.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(visibleDocuments.map((doc) => doc.id)))
    }
  }

  const handleSort = (column: typeof sortBy) => {
    if (sortBy === column) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(column)
      setSortDirection('asc')
    }
  }

  const renderSort = (column: typeof sortBy) => {
    if (sortBy !== column) return null
    return sortDirection === 'asc' ? ' ▲' : ' ▼'
  }

  const showingRange = useMemo(() => {
    if (documents.length === 0) return '0'
    const start = offset + 1
    const end = offset + documents.length
    return `${start}-${end}`
  }, [documents.length, offset])

  const handleDownloadSelected = async () => {
    if (!accessToken || selectedDocuments.length === 0) return
    setActionError(null)
    setDownloading(true)
    try {
      for (const doc of selectedDocuments) {
        const blob = await downloadDocument(accessToken, doc.id)
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = doc.file_name || `document-${doc.id}`
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(url)
      }
    } catch (err: any) {
      console.error('[Docs] download error', err)
      setActionError(err?.message || 'Failed to download selected documents.')
    } finally {
      setDownloading(false)
    }
  }

  const handleDeleteSelected = async () => {
    if (!accessToken || selectedDocuments.length === 0 || !isAdmin) return
    if (!window.confirm(`Delete ${selectedDocuments.length} document${selectedDocuments.length > 1 ? 's' : ''}? This action cannot be undone.`)) {
      return
    }
    setActionError(null)
    setDeleting(true)
    try {
      for (const doc of selectedDocuments) {
        await deleteDocument(accessToken, doc.id)
      }
      setDocuments((prev) => prev.filter((doc) => !selectedIds.has(doc.id)))
      setSelectedIds(new Set())
    } catch (err: any) {
      console.error('[Docs] delete error', err)
      setActionError(err?.message || 'Failed to delete selected documents.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-10">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold">Documents</h1>
            <p className="text-sm text-muted-foreground">
              Review the knowledge sources currently powering the canvas. To ingest new PDFs or manage retention, use the admin dashboard.
            </p>
          </div>

      <div className="rounded-2xl border border-border/70 bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold">Indexed Documents</p>
            <p className="text-xs text-muted-foreground">
              Showing {showingRange} of {totalCount} (page size {PAGE_SIZE})
            </p>
          </div>
          <div className="flex gap-6 text-sm">
            <div>
              <p className="text-muted-foreground text-xs uppercase tracking-wide">Total</p>
              <p className="font-semibold">{stats.count}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs uppercase tracking-wide">Size</p>
              <p className="font-semibold">{stats.totalSize}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <input
              type="search"
              placeholder="Search by name…"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value)
                setOffset(0)
              }}
              className="w-48 rounded-md border border-border/60 bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadSelected}
              disabled={selectedIds.size === 0 || !accessToken || downloading}
            >
              {downloading ? 'Downloading…' : 'Download Selected'}
            </Button>
            {isAdmin && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteSelected}
                disabled={selectedIds.size === 0 || deleting}
              >
                {deleting ? 'Deleting…' : 'Delete Selected'}
              </Button>
            )}
          </div>
        </div>

        {actionError && (
          <div className="mt-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {actionError}
          </div>
        )}

        {loading || docsLoading ? (
          <div className="py-12 text-center text-muted-foreground">Loading documents…</div>
        ) : error ? (
          <div className="mt-4 rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : documents.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            No documents available. Administrators can ingest PDFs from the Admin dashboard.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-muted-foreground border-b border-border/50">
                <tr>
                  <th className="py-2 pr-4">
                    <input
                      type="checkbox"
                      className="h-3 w-3"
                      checked={visibleDocuments.length > 0 && selectedIds.size === visibleDocuments.length}
                      onChange={toggleSelectAll}
                      aria-label="Select all documents"
                    />
                  </th>
                  <th className="py-2 pr-4 font-medium">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('title')}>
                      Title{renderSort('title')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 font-medium">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('type')}>
                      Type{renderSort('type')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 font-medium">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('product')}>
                      Product{renderSort('product')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 font-medium">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('chunks')}>
                      Chunks{renderSort('chunks')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 font-medium">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('size')}>
                      Size{renderSort('size')}
                    </button>
                  </th>
                  <th className="py-2 font-medium text-right">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('processed')}>
                      Processed{renderSort('processed')}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleDocuments.map((doc) => (
                  <tr key={doc.id} className="border-b border-border/30 last:border-b-0">
                    <td className="py-3 pr-4 align-top">
                      <input
                        type="checkbox"
                        className="h-3 w-3 mt-1"
                        checked={selectedIds.has(doc.id)}
                        onChange={() => toggleDocumentSelection(doc.id)}
                        aria-label={`Select ${doc.title || doc.file_name}`}
                      />
                    </td>
                    <td className="py-3 pr-4">
                      <div className="font-medium text-foreground">{doc.title || doc.file_name}</div>
                      <div className="text-xs text-muted-foreground">{doc.file_name}</div>
                    </td>
                    <td className="py-3 pr-4">{doc.document_type || '—'}</td>
                    <td className="py-3 pr-4">
                      {doc.product_name ? `${doc.product_name}${doc.product_version ? ` v${doc.product_version}` : ''}` : '—'}
                    </td>
                    <td className="py-3 pr-4">{doc.chunk_count}</td>
                    <td className="py-3 pr-4">{formatBytes(doc.file_size)}</td>
                    <td className="py-3 pr-4 text-right text-xs text-muted-foreground">{formatDate(doc.processed_at ?? doc.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Showing {showingRange} of {totalCount}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => {
                    setSelectedIds(new Set())
                    setOffset(Math.max(0, offset - PAGE_SIZE))
                  }}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + documents.length >= totalCount}
                  onClick={() => {
                    setSelectedIds(new Set())
                    setOffset(offset + PAGE_SIZE)
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
