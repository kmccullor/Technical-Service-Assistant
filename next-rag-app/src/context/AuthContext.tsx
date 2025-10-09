"use client";
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';

interface UserInfo {
  id: number;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  full_name: string;
  role_id: number;
  role_name?: string | null;
  status: string;
  verified: boolean;
}

interface AuthState {
  user: UserInfo | null;
  accessToken: string | null;
  refreshToken: string | null;
  expiresAt: number | null; // epoch ms
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<boolean>;
  register: (data: { email: string; password: string; first_name?: string; last_name?: string; role_id?: number }) => Promise<boolean>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = 'tsa_auth_v1';

function persist(state: Partial<AuthState>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (_) {}
}

function loadPersisted(): Partial<AuthState> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    expiresAt: null,
    loading: true,
    error: null,
  });

  const applyState = (patch: Partial<AuthState>) => setState(prev => ({ ...prev, ...patch }));

  // Load persisted tokens on mount
  useEffect(() => {
    const persisted = loadPersisted();
    if (persisted?.accessToken) {
      applyState({ ...persisted, loading: true });
      // Fetch profile
      fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${persisted.accessToken}` },
      })
        .then(r => (r.ok ? r.json() : null))
        .then(profile => {
          if (profile) {
            applyState({ user: profile, loading: false });
          } else {
            applyState({ loading: false, accessToken: null, refreshToken: null, user: null });
            persist({});
          }
        })
        .catch(() => {
          applyState({ loading: false });
        });
    } else {
      applyState({ loading: false });
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    applyState({ loading: true, error: null });
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const msg = (await res.json().catch(() => ({}))).detail || 'Login failed';
        applyState({ loading: false, error: msg });
        return false;
      }
      const data = await res.json();
      const expiresAt = Date.now() + data.expires_in * 1000 - 5000; // small buffer
      const newState: Partial<AuthState> = {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        expiresAt,
        user: data.user,
      };
      applyState({ ...newState, loading: false });
      persist(newState);
      return true;
    } catch (e) {
      applyState({ loading: false, error: 'Network error' });
      return false;
    }
  }, []);

  const register = useCallback(async (payload: { email: string; password: string; first_name?: string; last_name?: string; role_id?: number }) => {
    applyState({ loading: true, error: null });
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, role_id: payload.role_id || 2 }), // default employee role id=2
      });
      if (!res.ok) {
        const msg = (await res.json().catch(() => ({}))).detail || 'Registration failed';
        applyState({ loading: false, error: msg });
        return false;
      }
      // Auto-login requires email verified -> for now just success
      applyState({ loading: false });
      return true;
    } catch (e) {
      applyState({ loading: false, error: 'Network error' });
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    applyState({ user: null, accessToken: null, refreshToken: null, expiresAt: null });
    persist({});
  }, []);

  // Global 401 handling: monkey patch fetch once
  useEffect(() => {
    if ((globalThis as any)._tsaFetchWrapped) return;
    const original = fetch;
    (globalThis as any)._tsaFetchWrapped = true;
    (globalThis as any).fetch = async (...args: Parameters<typeof fetch>) => {
      const res = await original(...args);
      if (res.status === 401) {
        // Only trigger if not an auth endpoint to avoid loops
        const urlStr = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url;
        if (!urlStr.includes('/api/auth/login') && !urlStr.includes('/api/auth/register')) {
          logout();
          if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
            // simulate redirect
            try { (window as any).location.pathname = '/login'; } catch(_) {}
          }
        }
      }
      return res;
    };
  }, [logout]);

  const refresh = useCallback(async () => {
    if (!state.refreshToken) return;
    // Prevent concurrent / recursive refresh storms
    if ((refresh as any)._inFlight) return;
    (refresh as any)._inFlight = true;
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
      if (!res.ok) return logout();
      const data = await res.json();
      // If expires_in is very short (< 65s) we still apply a safety buffer but avoid immediate negative scheduling
      const rawMs = data.expires_in * 1000;
      const safetyBuffer = Math.min(5000, Math.max(1000, rawMs * 0.08)); // 8% or between 1s-5s
      const expiresAt = Date.now() + rawMs - safetyBuffer;
      const patch: Partial<AuthState> = {
        accessToken: data.access_token,
        expiresAt,
        user: data.user,
      };
      applyState(patch);
      persist({ ...patch, refreshToken: state.refreshToken });
    } catch (_) {
      logout();
    } finally {
      (refresh as any)._inFlight = false;
    }
  }, [state.refreshToken, logout]);

  // Auto refresh token 1 minute before expiry
  useEffect(() => {
    if (!state.expiresAt) return;
    // Schedule refresh at 12% before expiry (provides flexible window for varying lifetimes)
    const remaining = state.expiresAt - Date.now();
    if (remaining <= 0) {
      refresh();
      return;
    }
    const aheadFactor = 0.12;
    let timeoutMs = remaining - remaining * aheadFactor;
    // Avoid extremely small or negative timeouts which cause refresh loops
    if (timeoutMs < 1500) timeoutMs = Math.min(Math.max(remaining - 500, 0), 1500);
    const t = setTimeout(() => refresh(), timeoutMs);
    return () => clearTimeout(t);
  }, [state.expiresAt, refresh]);

  const value: AuthContextValue = {
    ...state,
    login,
    register,
    logout,
    refresh,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
