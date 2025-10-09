"use client";
import React, { useEffect } from 'react';
import { useAuth } from '@/src/context/AuthContext';

/**
 * RequireAuth wraps protected content and redirects unauthenticated users
 * to /login. While auth state is loading it renders a minimal placeholder.
 */
export const RequireAuth: React.FC<{ children: React.ReactNode; allow?: string[] }> = ({ children }) => {
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user && typeof window !== 'undefined') {
      try { window.location.href = '/login'; } catch (_) {}
    }
  }, [loading, user]);

  if (loading || (!user)) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        {loading ? 'Authenticating…' : 'Redirecting to login…'}
      </div>
    );
  }
  return <>{children}</>;
};

export default RequireAuth;