'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useAuth } from '@/contexts/auth-context';
import { setClientViewIdsForRequests } from '@/lib/api';

const LS_MODE = 'bastionfed_admin_view_mode';
const LS_CLIENT = 'bastionfed_admin_view_client_id';

function isTenantAdminRole(role: string | null | undefined): boolean {
  return role === 'owner' || role === 'admin';
}

export type AdminViewMode = 'tenant' | 'client';

export type ViewModeContextValue = {
  /** Use in useEffect deps to refetch when admin client view changes. */
  viewScopeKey: string;
  mode: AdminViewMode;
  setMode: (m: AdminViewMode) => void;
  selectedClientId: string | null;
  setSelectedClientId: (id: string | null) => void;
  canUseAdminClientView: boolean;
};

const ViewModeContext = createContext<ViewModeContextValue | null>(null);

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const { user, role, isDevMode, loading: authLoading } = useAuth();
  const [mode, setModeState] = useState<AdminViewMode>('tenant');
  const [selectedClientId, setSelectedClientIdState] = useState<string | null>(null);

  const canUseAdminClientView =
    !authLoading && !isDevMode && !!user && isTenantAdminRole(role);

  const setMode = useCallback(
    (m: AdminViewMode) => {
      if (authLoading || isDevMode || !user || !isTenantAdminRole(role)) {
        return;
      }
      setModeState(m);
      if (m === 'tenant') {
        setSelectedClientIdState(null);
      }
      if (typeof window === 'undefined') return;
      if (m === 'tenant') {
        window.localStorage.removeItem(LS_MODE);
        window.localStorage.removeItem(LS_CLIENT);
      } else {
        window.localStorage.setItem(LS_MODE, 'client');
      }
    },
    [authLoading, isDevMode, user, role],
  );

  const setSelectedClientId = useCallback(
    (id: string | null) => {
      if (authLoading || isDevMode || !user || !isTenantAdminRole(role)) {
        return;
      }
      setSelectedClientIdState(id);
      if (typeof window === 'undefined') return;
      if (id) window.localStorage.setItem(LS_CLIENT, id);
      else window.localStorage.removeItem(LS_CLIENT);
    },
    [authLoading, isDevMode, user, role],
  );

  useEffect(() => {
    if (authLoading) return;

    if (!user || isDevMode) {
      setModeState('tenant');
      setSelectedClientIdState(null);
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(LS_MODE);
        window.localStorage.removeItem(LS_CLIENT);
      }
      setClientViewIdsForRequests(null);
      return;
    }

    if (role === 'client_user') {
      setModeState('tenant');
      setSelectedClientIdState(null);
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(LS_MODE);
        window.localStorage.removeItem(LS_CLIENT);
      }
      setClientViewIdsForRequests(null);
      return;
    }

    if (isTenantAdminRole(role) && typeof window !== 'undefined') {
      const fromLs = window.localStorage.getItem(LS_MODE) === 'client' ? 'client' : 'tenant';
      setModeState(fromLs);
      setSelectedClientIdState(fromLs === 'client' ? window.localStorage.getItem(LS_CLIENT) : null);
      return;
    }

    // Session user but role not resolved yet — do not read admin LS or clear it.
  }, [authLoading, role, isDevMode, user?.uid]);

  const effectiveHeader =
    canUseAdminClientView && mode === 'client' && selectedClientId ? selectedClientId : null;

  if (typeof window !== 'undefined') {
    setClientViewIdsForRequests(effectiveHeader);
  }

  const viewScopeKey = effectiveHeader ?? 'tenant';

  const value = useMemo(
    () => ({
      viewScopeKey,
      mode,
      setMode,
      selectedClientId,
      setSelectedClientId,
      canUseAdminClientView,
    }),
    [viewScopeKey, mode, setMode, selectedClientId, setSelectedClientId, canUseAdminClientView],
  );

  return <ViewModeContext.Provider value={value}>{children}</ViewModeContext.Provider>;
}

export function useViewMode(): ViewModeContextValue {
  const ctx = useContext(ViewModeContext);
  if (!ctx) {
    return {
      viewScopeKey: 'tenant',
      mode: 'tenant',
      setMode: () => {},
      selectedClientId: null,
      setSelectedClientId: () => {},
      canUseAdminClientView: false,
    };
  }
  return ctx;
}
