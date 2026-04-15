'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading, isDevMode, sessionReady, accountModalOpen, adminWizardOpen } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user && !isDevMode) {
      router.replace('/');
    }
  }, [loading, user, isDevMode, router]);

  if (loading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 min-h-[calc(100vh-64px)] px-6">
        <div className="relative">
          <div
            className="absolute inset-0 rounded-full bg-white/[0.06] blur-xl scale-150"
            aria-hidden
          />
          <Loader2
            className="relative h-10 w-10 animate-spin text-white/45"
            strokeWidth={1.25}
            aria-hidden
          />
        </div>
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Verifying access</p>
        <span className="sr-only">Loading authentication</span>
      </div>
    );
  }

  if (!user && !isDevMode) {
    return null;
  }

  // While session isn't ready, still allow the shell when onboarding modals are open — they are
  // siblings to AuthGate content and sit above it; a full-page block here hid the account-type UI.
  if (user && !isDevMode && !sessionReady && !accountModalOpen && !adminWizardOpen) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 min-h-[calc(100vh-64px)] px-6">
        <Loader2 className="h-10 w-10 animate-spin text-white/45" strokeWidth={1.25} aria-hidden />
        <p className="max-w-xs text-center text-sm text-text-secondary">
          Connecting your workspace…
        </p>
        <span className="sr-only">Preparing session</span>
      </div>
    );
  }

  return <>{children}</>;
}
