import React from 'react'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import AdminPage from '@/app/admin/page'
import { AuthProvider, useAuth } from '@/src/context/AuthContext'

// Helper to preset auth state by writing localStorage before provider mounts
const seedAuth = (user: any) => {
  const state = {
    accessToken: 'ACCESS123',
    refreshToken: 'REFRESH123',
    expiresAt: Date.now() + 60_000,
    user
  }
  window.localStorage.setItem('tsa_auth_v1', JSON.stringify(state))
}

describe('AdminPage', () => {
  beforeEach(() => {
    delete (globalThis as any)._tsaFetchWrapped
    const store: Record<string,string> = {}
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: (k: string) => store[k] || null,
        setItem: (k: string, v: string) => { store[k] = v },
        removeItem: (k: string) => { delete store[k] },
        clear: () => { Object.keys(store).forEach(k => delete store[k]) }
      },
      configurable: true
    })
  })

  it('renders users and roles tables for admin', async () => {
    const adminUser = {
      id: 1,
      email: 'admin@example.com',
      first_name: 'Admin',
      last_name: 'User',
      full_name: 'Admin User',
      role_id: 1,
      role_name: 'admin',
      status: 'active',
      verified: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    seedAuth(adminUser)

    global.fetch = jest.fn(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/auth/me')) {
        return { ok: true, json: async () => adminUser }
      }
      if (url.startsWith('/api/admin/users')) {
        return { ok: true, json: async () => ({ users: [adminUser], total: 1, page: 1, page_size: 50 }) }
      }
      if (url.startsWith('/api/admin/roles')) {
        return { ok: true, json: async () => ([
          { id: 1, name: 'admin', description: 'Administrator', system: true, permissions: ['user.manage'] },
          { id: 2, name: 'employee', description: 'Employee', system: true, permissions: [] }
        ]) }
      }
      if (url.includes('/api/admin/users/') && init?.method === 'PATCH') {
        return { ok: true, json: async () => ({ ...adminUser, role_id: 1 }) }
      }
      return { ok: true, json: async () => ({}) }
    }) as any

    await act(async () => {
      render(<AuthProvider><AdminPage /></AuthProvider>)
    })

    await waitFor(() => expect(screen.getByText(/admin dashboard/i)).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('admin@example.com')).toBeInTheDocument())
    const usersHeadings = screen.getAllByText(/users/i)
    expect(usersHeadings.length).toBeGreaterThan(0)
    const rolesHeadings = screen.getAllByText(/roles/i)
    expect(rolesHeadings.length).toBeGreaterThan(0)
  })

  it('updates user role via select change', async () => {
    const adminUser = {
      id: 1,
      email: 'admin@example.com',
      first_name: 'Admin',
      last_name: 'User',
      full_name: 'Admin User',
      role_id: 1,
      role_name: 'admin',
      status: 'active',
      verified: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    seedAuth(adminUser)

    const fetchMock = jest.fn(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/auth/me')) {
        return { ok: true, json: async () => adminUser }
      }
      if (url.startsWith('/api/admin/users')) {
        return { ok: true, json: async () => ({ users: [adminUser], total: 1, page: 1, page_size: 50 }) }
      }
      if (url.startsWith('/api/admin/roles')) {
        return { ok: true, json: async () => ([
          { id: 1, name: 'admin', description: 'Administrator', system: true, permissions: ['user.manage'] },
          { id: 2, name: 'employee', description: 'Employee', system: true, permissions: [] }
        ]) }
      }
      if (url.includes('/api/admin/users/') && init?.method === 'PATCH') {
        const body = JSON.parse(init.body as string)
        return { ok: true, json: async () => ({ ...adminUser, role_id: body.role_id ?? adminUser.role_id }) }
      }
      return { ok: true, json: async () => ({}) }
    }) as any
    global.fetch = fetchMock

    await act(async () => {
      render(<AuthProvider><AdminPage /></AuthProvider>)
    })
    await waitFor(() => expect(screen.getByText(/admin dashboard/i)).toBeInTheDocument())
    const roleSelect = screen.getAllByRole('combobox').find(sel => (sel as HTMLSelectElement).value === '1') as HTMLSelectElement
    await act(async () => {
      fireEvent.change(roleSelect, { target: { value: '1' } })
    })
    // verify PATCH call executed
  expect(fetchMock.mock.calls.some((call: any[]) => (typeof call[0] === 'string' && call[0].includes('/api/admin/users/1') && call[1]?.method === 'PATCH'))).toBe(true)
  })
})
