'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
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

  const fetchDocuments = async () => {
    if (!accessToken) {
      setDocuments([])
      setDocsLoading(false)
      return
    }
    try {
      setDocsLoading(true)
      const response = await listDocuments({ accessToken, limit: 50 })
      setDocuments(response.documents ?? [])
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
  }, [accessToken])

  const stats = useMemo(() => {
    const totalSize = documents.reduce((sum, doc) => sum + (doc.file_size ?? 0), 0)
    return {
      count: documents.length,
      totalSize: formatBytes(totalSize),
    }
  }, [documents])

  const isAdmin = user?.role_name?.toLowerCase() === 'admin'
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [downloading, setDownloading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

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
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(documents.map((doc) => doc.id)))
    }
  }

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
            <p className="text-xs text-muted-foreground">Showing the most recent 50 entries.</p>
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
          <div className="flex flex-wrap gap-2 text-sm">
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
            {isAdmin && (
              <Link href="/admin" className="text-xs text-primary underline-offset-4 hover:underline self-center">
                Manage in Admin
              </Link>
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
                      checked={documents.length > 0 && selectedIds.size === documents.length}
                      onChange={toggleSelectAll}
                      aria-label="Select all documents"
                    />
                  </th>
                  <th className="py-2 pr-4 font-medium">Title</th>
                  <th className="py-2 pr-4 font-medium">Type</th>
                  <th className="py-2 pr-4 font-medium">Product</th>
                  <th className="py-2 pr-4 font-medium">Chunks</th>
                  <th className="py-2 pr-4 font-medium">Size</th>
                  <th className="py-2 font-medium text-right">Processed</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
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
          </div>
        )}
      </div>
    </div>
  )
}
