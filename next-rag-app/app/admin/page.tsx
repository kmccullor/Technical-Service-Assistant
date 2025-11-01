'use client'

import React, { useEffect, useState } from 'react'
import { useAuth } from '@/src/context/AuthContext'
import { listUsers, listRoles, updateUser, updateRole, createUser, deleteUser, AdminUser, RoleInfo, AdminUserStatus, listDocuments, deleteDocument, downloadDocument, DocumentInfo } from '@/lib/admin'
import Link from 'next/link'
import { Shield, RefreshCw } from 'lucide-react'

export default function AdminPage() {
  const { user, accessToken, loading } = useAuth() as any
  const [users, setUsers] = useState<AdminUser[]>([])
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [adminLoading, setAdminLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [documentSearch, setDocumentSearch] = useState('')
  const [updatingUser, setUpdatingUser] = useState<number | null>(null)
  const [updatingRole, setUpdatingRole] = useState<number | null>(null)
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [createUserForm, setCreateUserForm] = useState({ email: '', password: '', first_name: '', last_name: '', role_id: 2 })
  const [creatingUser, setCreatingUser] = useState(false)
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null)
  const [deletingDocumentId, setDeletingDocumentId] = useState<number | null>(null)

  useEffect(() => {
    if (!accessToken) return
    if (!user || user.role_name !== 'admin') return
    refreshAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, user?.role_name])

  useEffect(() => {
    if (!accessToken || !user || user.role_name !== 'admin') return
    // Refresh documents when search changes
    const refreshDocuments = async () => {
      try {
        const d = await listDocuments({ accessToken, search_term: documentSearch, limit: 50 })
        setDocuments(Array.isArray(d?.documents) ? d.documents : [])
      } catch (e: any) {
        console.error('Failed to refresh documents:', e)
      }
    }
    refreshDocuments()
  }, [documentSearch, accessToken, user])

  const refreshAll = async () => {
    try {
  setAdminLoading(true)
      const [u, r, d] = await Promise.all([
        listUsers({ accessToken, search }),
        listRoles(accessToken),
        listDocuments({ accessToken, search_term: documentSearch, limit: 50 }),
      ])
      setUsers(Array.isArray(u?.users) ? u.users : [])
      setRoles(Array.isArray(r) ? r : [])
      setDocuments(Array.isArray(d?.documents) ? d.documents : [])
      setError(null)
    } catch (e: any) {
      setError(e.message || 'Failed to load admin data')
    } finally {
  setAdminLoading(false)
    }
  }

  const handleUserRoleChange = async (id: number, role_id: number) => {
    try {
      setUpdatingUser(id)
      const updated = await updateUser(accessToken, id, { role_id })
      setUsers(prev => prev.map(u => u.id === id ? updated : u))
    } catch (e: any) {
      alert(e.message)
    } finally {
      setUpdatingUser(null)
    }
  }

  const handleUserStatusChange = async (id: number, status: AdminUserStatus) => {
    try {
      setUpdatingUser(id)
      const updated = await updateUser(accessToken, id, { status })
      setUsers(prev => prev.map(u => u.id === id ? updated : u))
    } catch (e: any) {
      alert(e.message)
    } finally {
      setUpdatingUser(null)
    }
  }

  const handleRoleDescriptionChange = async (id: number, description: string) => {
    try {
      setUpdatingRole(id)
      const updated = await updateRole(accessToken, id, { description })
      setRoles(prev => prev.map(r => r.id === id ? updated : r))
    } catch (e: any) {
      alert(e.message)
    } finally {
      setUpdatingRole(null)
    }
  }

  const handleDeleteUser = async (id: number) => {
    const target = users.find(u => u.id === id)
    if (!target) return
    if (!confirm(`Delete user ${target.email}? This action cannot be undone.`)) return
    try {
      setDeletingUserId(id)
      await deleteUser(accessToken, id)
      setUsers(prev => prev.filter(u => u.id !== id))
    } catch (e:any) {
      alert(e.message || 'Failed to delete user')
    } finally {
      setDeletingUserId(null)
    }
  }

  const handleDeleteDocument = async (id: number) => {
    const target = documents.find(d => d.id === id)
    if (!target) return
    if (!confirm(`Delete document "${target.file_name}"? This will remove all associated chunks and cannot be undone.`)) return
    try {
      setDeletingDocumentId(id)
      await deleteDocument(accessToken, id)
      setDocuments(prev => prev.filter(d => d.id !== id))
    } catch (e:any) {
      alert(e.message || 'Failed to delete document')
    } finally {
      setDeletingDocumentId(null)
    }
  }

  const handleDownloadDocument = async (id: number) => {
    const target = documents.find(d => d.id === id)
    if (!target) return
    try {
      const blob = await downloadDocument(accessToken, id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = target.file_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (e:any) {
      alert(e.message || 'Failed to download document')
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createUserForm.email || !createUserForm.password) {
      alert('Email and password are required')
      return
    }
    try {
      setCreatingUser(true)
      const newUser = await createUser(accessToken, createUserForm)
      setUsers(prev => [newUser, ...prev])
      setCreateUserForm({ email: '', password: '', first_name: '', last_name: '', role_id: 2 })
      setShowCreateUser(false)
      alert('User created successfully!')
    } catch (e: any) {
      alert(e.message || 'Failed to create user')
    } finally {
      setCreatingUser(false)
    }
  }

  if (loading || adminLoading) {
    return <div className="flex items-center justify-center h-screen text-muted-foreground">Loading...</div>
  }
  if (!user) {
    return (
      <div className="p-8 text-center space-y-4">
        <h1 className="text-2xl font-semibold">Authentication Required</h1>
        <p className="text-muted-foreground">You must be logged in to view this page.</p>
        <Link href="/login" className="underline">Go to Login</Link>
      </div>
    )
  }

  if (user.role_name !== 'admin') {
    return <div className="p-8 text-center space-y-4">
      <h1 className="text-2xl font-semibold">Access Denied</h1>
      <p className="text-muted-foreground">You do not have permission to view administrative controls.</p>
      <Link href="/" className="underline">Return Home</Link>
    </div>
  }

  const safeRoles = Array.isArray(roles) ? roles : []
  const safeUsers = Array.isArray(users) ? users : []

  return (
    <div className="flex flex-col h-screen">
      <div className="border-b p-4 flex items-center justify-between bg-muted/30">
        <div className="flex items-center gap-2">
          <Link href="/" className="text-muted-foreground hover:text-foreground mr-2">← Back</Link>
          <Shield className="h-5 w-5" />
          <h1 className="text-xl font-semibold">Admin Dashboard</h1>
        </div>
        <div className="flex items-center gap-3">
          <input
            className="border rounded px-2 py-1 text-sm"
            placeholder="Search users"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <input
            className="border rounded px-2 py-1 text-sm"
            placeholder="Search documents"
            value={documentSearch}
            onChange={e => setDocumentSearch(e.target.value)}
          />
          <button
            onClick={refreshAll}
            className="inline-flex items-center gap-1 border rounded px-3 py-1 text-sm hover:bg-muted"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>
      </div>
      {error && <div className="p-4 text-sm text-red-600">{error}</div>}
      {adminLoading ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">Loading...</div>
      ) : (
        <div className="flex-1 overflow-auto p-6 space-y-10">
          <section>
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-medium">Users</h2>
              <button
                onClick={() => setShowCreateUser(!showCreateUser)}
                className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90"
              >
                {showCreateUser ? 'Cancel' : 'Add User'}
              </button>
            </div>

            {showCreateUser && (
              <div className="mb-4 p-4 border rounded bg-muted/20">
                <h3 className="text-md font-medium mb-3">Create New User</h3>
                <form onSubmit={handleCreateUser} className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Email *</label>
                    <input
                      type="email"
                      required
                      value={createUserForm.email}
                      onChange={e => setCreateUserForm(prev => ({ ...prev, email: e.target.value }))}
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Password *</label>
                    <input
                      type="password"
                      required
                      value={createUserForm.password}
                      onChange={e => setCreateUserForm(prev => ({ ...prev, password: e.target.value }))}
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">First Name</label>
                    <input
                      type="text"
                      value={createUserForm.first_name}
                      onChange={e => setCreateUserForm(prev => ({ ...prev, first_name: e.target.value }))}
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Last Name</label>
                    <input
                      type="text"
                      value={createUserForm.last_name}
                      onChange={e => setCreateUserForm(prev => ({ ...prev, last_name: e.target.value }))}
                      className="w-full border rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Role</label>
                    <select
                      value={createUserForm.role_id}
                      onChange={e => setCreateUserForm(prev => ({ ...prev, role_id: Number(e.target.value) }))}
                      className="w-full border rounded px-2 py-1 text-sm"
                    >
                      {safeRoles.map(r => (
                        <option key={r.id} value={r.id}>{r.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      disabled={creatingUser}
                      className="px-4 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                    >
                      {creatingUser ? 'Creating...' : 'Create User'}
                    </button>
                  </div>
                </form>
              </div>
            )}

            <div className="overflow-x-auto border rounded">
              <table className="min-w-full text-sm">
                <thead className="bg-muted/50">
                  <tr className="text-left">
                    <th className="p-2">ID</th>
                    <th className="p-2">Email</th>
                    <th className="p-2">Name</th>
                    <th className="p-2">Role</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Verified</th>
                    <th className="p-2">Updated</th>
                    <th className="p-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {safeUsers.map(u => (
                    <tr key={u.id} className="border-t">
                      <td className="p-2 font-mono text-xs">{u.id}</td>
                      <td className="p-2">{u.email}</td>
                      <td className="p-2">{u.full_name}</td>
                      <td className="p-2">
                        <select
                          className="border rounded px-1 py-0.5 text-xs"
                          value={u.role_id}
                          disabled={updatingUser === u.id}
                          onChange={e => handleUserRoleChange(u.id, Number(e.target.value))}
                        >
                          {safeRoles.map(r => (
                            <option key={r.id} value={r.id}>{r.name}</option>
                          ))}
                        </select>
                      </td>
                      <td className="p-2">
                        <select
                          className="border rounded px-1 py-0.5 text-xs"
                          value={u.status}
                          disabled={updatingUser === u.id}
                          onChange={e => handleUserStatusChange(u.id, e.target.value as AdminUserStatus)}
                        >
                          <option value="active">active</option>
                          <option value="disabled">disabled</option>
                          <option value="pending">pending</option>
                        </select>
                      </td>
                      <td className="p-2 text-center">{u.verified ? '✅' : '❌'}</td>
                      <td className="p-2 text-xs text-muted-foreground">{u.updated_at?.replace('T', ' ').substring(0,16)}</td>
                      <td className="p-2">
                        <button
                          onClick={() => handleDeleteUser(u.id)}
                          disabled={deletingUserId === u.id || u.id === user.id}
                          className="text-xs px-2 py-0.5 rounded border border-red-600 text-red-600 hover:bg-red-600 hover:text-white disabled:opacity-40"
                          title={u.id === user.id ? 'Cannot delete current logged in user' : 'Delete user'}
                        >{deletingUserId === u.id ? 'Deleting...' : 'Delete'}</button>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr><td colSpan={8} className="p-4 text-center text-muted-foreground">No users found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-medium mb-3">Roles</h2>
            <div className="overflow-x-auto border rounded">
              <table className="min-w-full text-sm">
                <thead className="bg-muted/50">
                  <tr className="text-left">
                    <th className="p-2">ID</th>
                    <th className="p-2">Name</th>
                    <th className="p-2">Description</th>
                    <th className="p-2">System</th>
                    <th className="p-2">Permissions</th>
                  </tr>
                </thead>
                <tbody>
                  {safeRoles.map(r => (
                    <tr key={r.id} className="border-t">
                      <td className="p-2 font-mono text-xs">{r.id}</td>
                      <td className="p-2 font-medium">{r.name}</td>
                      <td className="p-2">
                        {r.system ? (
                          <span className="text-muted-foreground text-xs">{r.description || '—'}</span>
                        ) : (
                          <input
                            className="border rounded px-1 py-0.5 text-xs w-56"
                            defaultValue={r.description || ''}
                            disabled={updatingRole === r.id}
                            onBlur={e => {
                              if (e.target.value !== r.description) {
                                handleRoleDescriptionChange(r.id, e.target.value)
                              }
                            }}
                          />
                        )}
                      </td>
                      <td className="p-2 text-center">{r.system ? '🔒' : ''}</td>
                      <td className="p-2 text-xs">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {(r.permissions || []).map(p => (
                            <span key={p} className="px-1.5 py-0.5 rounded bg-secondary text-[10px] tracking-wide uppercase">{p}</span>
                          ))}
                          {(!r.permissions || r.permissions.length === 0) && <span className="text-muted-foreground">—</span>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
             </div>
           </section>

           <section>
             <h2 className="text-lg font-medium mb-3">Documents</h2>
             <div className="overflow-x-auto border rounded">
               <table className="min-w-full text-sm">
                 <thead className="bg-muted/50">
                   <tr className="text-left">
                     <th className="p-2">ID</th>
                     <th className="p-2">File Name</th>
                     <th className="p-2">Title</th>
                     <th className="p-2">Type</th>
                     <th className="p-2">Product</th>
                     <th className="p-2">Privacy</th>
                     <th className="p-2">Chunks</th>
                     <th className="p-2">Size</th>
                     <th className="p-2">Created</th>
                     <th className="p-2">Actions</th>
                   </tr>
                 </thead>
                 <tbody>
                   {documents.map(d => (
                     <tr key={d.id} className="border-t">
                       <td className="p-2 font-mono text-xs">{d.id}</td>
                       <td className="p-2 max-w-xs truncate" title={d.file_name}>{d.file_name}</td>
                       <td className="p-2 max-w-xs truncate" title={d.title || ''}>{d.title || '—'}</td>
                       <td className="p-2">{d.document_type || '—'}</td>
                       <td className="p-2">{d.product_name || '—'}</td>
                       <td className="p-2">
                         <span className={`px-1.5 py-0.5 rounded text-xs ${
                           d.privacy_level === 'public' ? 'bg-green-100 text-green-800' :
                           d.privacy_level === 'internal' ? 'bg-yellow-100 text-yellow-800' :
                           'bg-red-100 text-red-800'
                         }`}>
                           {d.privacy_level}
                         </span>
                       </td>
                       <td className="p-2 text-center">{d.chunk_count}</td>
                       <td className="p-2 text-xs text-muted-foreground">
                         {d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : '—'}
                       </td>
                       <td className="p-2 text-xs text-muted-foreground">
                         {new Date(d.created_at).toLocaleDateString()}
                       </td>
                        <td className="p-2">
                          <div className="flex gap-1">
                            <button
                              onClick={() => handleDownloadDocument(d.id)}
                              className="text-xs px-2 py-0.5 rounded border border-blue-600 text-blue-600 hover:bg-blue-600 hover:text-white"
                              title="Download document"
                            >
                              Download
                            </button>
                            <button
                              onClick={() => handleDeleteDocument(d.id)}
                              disabled={deletingDocumentId === d.id}
                              className="text-xs px-2 py-0.5 rounded border border-red-600 text-red-600 hover:bg-red-600 hover:text-white disabled:opacity-40"
                              title="Delete document"
                            >
                              {deletingDocumentId === d.id ? 'Deleting...' : 'Delete'}
                            </button>
                          </div>
                        </td>
                     </tr>
                   ))}
                   {documents.length === 0 && (
                     <tr><td colSpan={10} className="p-4 text-center text-muted-foreground">No documents found.</td></tr>
                   )}
                 </tbody>
               </table>
             </div>
           </section>
         </div>
       )}
     </div>
   )
 }
