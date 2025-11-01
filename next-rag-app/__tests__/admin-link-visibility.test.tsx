import React from 'react'
import { render, screen, act } from '@testing-library/react'
import '@testing-library/jest-dom';
import 'whatwg-fetch'
import { AuthProvider, useAuth } from '@/src/context/AuthContext'
import { Sidebar } from '@/components/layout/sidebar'

// Helper to mount sidebar within auth context
function SidebarWrapper() {
  const { user } = useAuth()
  if (!user) return <div>No user</div>
  return <Sidebar onNewChat={() => {}} onSelectConversation={() => {}} />
}

describe('Admin link visibility', () => {
  beforeEach(() => {
    delete (globalThis as any)._tsaFetchWrapped;
    const store: Record<string, string> = {};
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: (k: string) => store[k] || null,
        setItem: (k: string, v: string) => { store[k] = v },
        removeItem: (k: string) => { delete store[k] },
        clear: () => { Object.keys(store).forEach(k => delete store[k]) },
      },
      writable: true,
    });
  });

  it('shows Admin link for admin role', async () => {
    global.fetch = jest.fn(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString();
      // Debug log
      // eslint-disable-next-line no-console
      console.log('FETCH CALLED:', url);
      if (url.endsWith('/api/auth/me')) {
        return new Response(JSON.stringify({
          id: 1,
          email: 'admin@example.com',
          first_name: 'Admin',
          last_name: 'User',
          full_name: 'Admin User',
          role_id: 1,
          role_name: 'admin',
          status: 'active',
          verified: true,
        }), { status: 200 });
      }
      if (url.endsWith('/api/auth/refresh')) {
        // Return correct field names and structure
        return new Response(JSON.stringify({
          access_token: 'X',
          refresh_token: 'R',
          expires_in: 60,
          user: {
            id: 1,
            email: 'admin@example.com',
            first_name: 'Admin',
            last_name: 'User',
            full_name: 'Admin User',
            role_id: 1,
            role_name: 'admin',
            status: 'active',
            verified: true,
          }
        }), { status: 200 });
      }
      if (url.endsWith('/api/stats')) return new Response(JSON.stringify({ documents: 0, chunks: 0 }), { status: 200 });
      if (url.endsWith('/api/conversations')) return new Response(JSON.stringify([]), { status: 200 });
      return new Response('{}', { status: 200 });
    });
    window.localStorage.setItem('tsa_auth_v1', JSON.stringify({ accessToken: 'X', refreshToken: 'R', expiresAt: Date.now() + 60000 }));
    await act(async () => {
      render(<AuthProvider><SidebarWrapper /></AuthProvider>);
    });
    // Wait for 'No user' to disappear (user context loads)
    await screen.findByText('Data Dictionary');
    expect(screen.getByText('Admin')).toBeInTheDocument();
  });

  it('does not show Admin link for non-admin role', async () => {
    global.fetch = jest.fn(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/api/auth/me')) {
        return new Response(JSON.stringify({
          id: 2,
          email: 'user@example.com',
          first_name: 'Normal',
          last_name: 'User',
          full_name: 'Normal User',
          role_id: 2,
          role_name: 'employee',
          status: 'active',
          verified: true,
        }), { status: 200 });
      }
      if (url.endsWith('/api/auth/refresh')) {
        // Return correct field names and structure
        return new Response(JSON.stringify({
          access_token: 'X',
          refresh_token: 'R',
          expires_in: 60,
          user: {
            id: 2,
            email: 'user@example.com',
            first_name: 'Normal',
            last_name: 'User',
            full_name: 'Normal User',
            role_id: 2,
            role_name: 'employee',
            status: 'active',
            verified: true,
          }
        }), { status: 200 });
      }
      if (url.endsWith('/api/stats')) return new Response(JSON.stringify({ documents: 0, chunks: 0 }), { status: 200 });
      if (url.endsWith('/api/conversations')) return new Response(JSON.stringify([]), { status: 200 });
      return new Response('{}', { status: 200 });
    });
    window.localStorage.setItem('tsa_auth_v1', JSON.stringify({ accessToken: 'X', refreshToken: 'R', expiresAt: Date.now() + 60000 }));
    await act(async () => {
      render(<AuthProvider><SidebarWrapper /></AuthProvider>);
    });
    // Wait for 'No user' to disappear (user context loads)
    await screen.findByText('Data Dictionary');
    expect(screen.queryByText('Admin')).toBeNull();
  });
})
