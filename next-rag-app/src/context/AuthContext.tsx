"use client";
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

export interface UserInfo {
  id: number;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  full_name: string;
  role_id: number;
  role_name?: string | null;
  status: string;
  verified: boolean;
  password_change_required?: boolean;
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

  // Helper to build backend URL (supports optional NEXT_PUBLIC_BACKEND_URL or falls back to relative path + rewrites)
  const backendUrl = (path: string) => {
    const base = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (base && /^https?:\/\//.test(base)) {
      return base.replace(/\/$/, '') + path;
    }
    return path; // rely on Next.js rewrite proxy
  };

  // Load persisted tokens on mount with backend health + guarded profile fetch
  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      console.log('[AUTH] Initializing auth context');
      const persisted = loadPersisted();
      console.log('[AUTH] Persisted state:', persisted ? 'Found tokens' : 'No tokens');
      if (!persisted?.accessToken) {
        console.log('[AUTH] No access token found, setting loading false');
        if (!cancelled) applyState({ loading: false });
        return;
      }
      console.log('[AUTH] Found access token, loading user profile');
      applyState({ ...persisted, loading: true });
      // Health check first to avoid white screen if backend not ready
      try {
        const health = await fetch(backendUrl('/api/auth/health')).catch(() => null);
        // If health endpoint absent (404) or backend down, we degrade gracefully instead of blocking UI
        if (!health || (!health.ok && health.status !== 404)) {
          if (!cancelled) applyState({ loading: false, error: 'Auth service unavailable' });
          return;
        }
      } catch (_) {
        if (!cancelled) applyState({ loading: false, error: 'Auth service unavailable' });
        return;
      }
      try {
        console.log('[AUTH] Fetching user profile from /api/auth/me');
        const r = await fetch(backendUrl('/api/auth/me'), { headers: { Authorization: `Bearer ${persisted.accessToken}` } });
        console.log('[AUTH] Profile fetch response status:', r.status);
        if (r.ok) {
          const profile = await r.json();
          console.log('[AUTH] Profile loaded:', { id: profile.id, email: profile.email, password_change_required: profile.password_change_required });
          if (!cancelled) applyState({ user: profile, loading: false });
        } else {
          if (!cancelled) {
            applyState({ loading: false, accessToken: null, refreshToken: null, user: null });
            persist({});
          }
        }
      } catch (_) {
        if (!cancelled) applyState({ loading: false });
      }
    };
    init();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    console.log('[AUTH] Login attempt for:', email);
    applyState({ loading: true, error: null });
    try {
      console.log('[AUTH] Sending login request to:', backendUrl('/api/auth/login'));
      const res = await fetch(backendUrl('/api/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      console.log('[AUTH] Login response status:', res.status);
      if (!res.ok) {
        let msg = 'Login failed';
        try {
          const errJson = await res.json();
          if (errJson && typeof errJson.detail === 'string') msg = errJson.detail;
        } catch (_) { /* swallow */ }
        applyState({ loading: false, error: msg });
        return false;
      }
      let data: any = null;
      try {
        data = await res.json();
      } catch (_) {
        applyState({ loading: false, error: 'Malformed server response' });
        return false;
      }
      // Guard required fields
      console.log('[AUTH] Login response data:', { hasAccessToken: !!data.access_token, hasRefreshToken: !!data.refresh_token, hasUser: !!data.user, userPasswordChangeRequired: data.user?.password_change_required });
      if (!data || typeof data !== 'object' || !data.access_token || !data.refresh_token || typeof data.expires_in !== 'number' || !data.user) {
        console.log('[AUTH] Invalid login response data');
        applyState({ loading: false, error: 'Unexpected auth response' });
        return false;
      }
      const safeExpires = Number.isFinite(data.expires_in) ? data.expires_in : 0;
      const expiresAt = Date.now() + Math.max(0, safeExpires * 1000 - 5000);
      const newState: Partial<AuthState> = {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        expiresAt,
        user: data.user,
      };
      console.log('[AUTH] Login successful, setting user state:', { email: data.user.email, password_change_required: data.user.password_change_required });
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
      const res = await fetch(backendUrl('/api/auth/register'), {
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
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      if (!path.startsWith('/login')) {
        try { window.location.href = '/login'; } catch (_) {}
      }
    }
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
    console.log('[AUTH] Refresh called');
    if (!state.refreshToken) {
      console.log('[AUTH] No refresh token available');
      return;
    }
    // Prevent concurrent / recursive refresh storms
    if ((refresh as any)._inFlight) {
      console.log('[AUTH] Refresh already in flight');
      return;
    }
    console.log('[AUTH] Starting token refresh');
    (refresh as any)._inFlight = true;
    try {
      const res = await fetch(backendUrl('/api/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
      console.log('[AUTH] Refresh response status:', res.status);
      if (!res.ok) {
        console.log('[AUTH] Refresh failed, logging out');
        return logout();
      }
      const data = await res.json();
      console.log('[AUTH] Refresh successful, updated user:', { email: data.user?.email, password_change_required: data.user?.password_change_required });
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
