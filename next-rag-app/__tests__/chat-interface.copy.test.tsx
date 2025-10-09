import { render, screen, fireEvent, waitFor } from '@testing-library/react';
// Mock fetch for AuthProvider
beforeAll(() => {
  global.fetch = jest.fn(async (input) => {
    const url = typeof input === 'string' ? input : input.toString();
    if (url.endsWith('/api/auth/me')) {
      return new Response(JSON.stringify({
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        full_name: 'Test User',
        role_id: 2,
        role_name: 'employee',
        status: 'active',
        verified: true,
      }), { status: 200 });
    }
    return new Response('{}', { status: 200 });
  });
  window.localStorage.setItem('tsa_auth_v1', JSON.stringify({ accessToken: 'X', refreshToken: 'R', expiresAt: Date.now() + 60000 }));
});

afterAll(() => {
  (global.fetch as any) = undefined;
});
import '@testing-library/jest-dom';
import { ChatInterface } from '../components/chat/chat-interface';
import React from 'react';


// Mock clipboard API
Object.defineProperty(global.navigator, 'clipboard', {
  value: {
    writeText: jest.fn().mockResolvedValue(undefined),
  },
  writable: true,
});

// Mock scrollIntoView for jsdom
window.HTMLElement.prototype.scrollIntoView = jest.fn();

import { act } from 'react-dom/test-utils';

import { AuthProvider } from '@/src/context/AuthContext';

describe('ChatInterface copy response feature', () => {
  it('shows toast when copy is successful', async () => {
    render(
      <AuthProvider>
        <ChatInterface />
      </AuthProvider>
    );
    const textarea = screen.getByPlaceholderText('Ask a question about your documents...');
    fireEvent.change(textarea, { target: { value: 'Hello assistant' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });
    const copyBtn = await screen.findByTestId('copy-btn', {}, { timeout: 2000 });
    fireEvent.click(copyBtn);
    await waitFor(() => {
      expect(screen.getByText('Copied to clipboard!')).toBeInTheDocument();
    });
  });

  it('shows error toast when copy fails', async () => {
    (global.navigator.clipboard.writeText as jest.Mock).mockRejectedValueOnce(new Error('fail'));
    render(
      <AuthProvider>
        <ChatInterface />
      </AuthProvider>
    );
    const textarea = screen.getByPlaceholderText('Ask a question about your documents...');
    fireEvent.change(textarea, { target: { value: 'Hello assistant' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });
    const copyBtn = await screen.findByTestId('copy-btn', {}, { timeout: 2000 });
    fireEvent.click(copyBtn);
    await waitFor(() => {
      expect(screen.getByText('Copy failed')).toBeInTheDocument();
    });
  });
});
