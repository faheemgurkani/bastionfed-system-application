'use client';

import { Suspense, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, Loader2, Mail } from 'lucide-react';
import { PENDING_CLIENT_INVITE_KEY } from '@/contexts/auth-context';
import { useAuth } from '@/contexts/auth-context';

function AcceptClientInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, loading, sessionReady, tenantId } = useAuth();
  const hasToken = Boolean(searchParams.get('token')?.trim());

  useEffect(() => {
    const token = searchParams.get('token');
    if (token && typeof window !== 'undefined') {
      sessionStorage.setItem(PENDING_CLIENT_INVITE_KEY, token);
    }
  }, [searchParams]);

  useEffect(() => {
    if (loading) return;
    if (user && sessionReady && tenantId) {
      router.replace('/dashboard');
    }
  }, [loading, user, sessionReady, tenantId, router]);

  const phase: 'loading' | 'needs-signin' | 'completing' | 'missing-token' = loading
    ? 'loading'
    : !hasToken
      ? 'missing-token'
      : !user
        ? 'needs-signin'
        : 'completing';

  return (
    <main className="relative min-h-screen bg-bg-base text-text-primary">
      <div className="grid-bg fixed inset-0 opacity-[0.35]" aria-hidden />
      <div className="noise-overlay" aria-hidden />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-5 py-16">
        <div className="bastionfed-onboard-surface w-full max-w-md rounded-2xl border border-white/[0.08] bg-bg-surface/95 p-8 shadow-[0_24px_80px_-24px_rgba(0,0,0,0.9)] ring-1 ring-white/[0.04] backdrop-blur-sm sm:p-10">
          <div className="mb-8 flex justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
              <Mail className="h-7 w-7 text-white/80" aria-hidden />
            </div>
          </div>

          <h1 className="text-center font-display text-2xl font-bold tracking-tight text-white">
            Client invite
          </h1>
          <p className="mt-3 text-center text-sm leading-relaxed text-text-secondary">
            {phase === 'missing-token' ? (
              <>
                This link is missing a valid token. Ask your administrator for a new invite link, or open the full URL
                they sent you.
              </>
            ) : phase === 'needs-signin' ? (
              <>
                Sign in with the <span className="text-white/90">same email</span> your admin used on the invite —
                Google or email/password. We&apos;ll attach access right after you sign in.
              </>
            ) : (
              <>
                Hang tight — we&apos;re finishing your access. If nothing changes, confirm your signed-in email matches
                the invite.
              </>
            )}
          </p>

          <div className="mt-8 flex min-h-[4.5rem] flex-col items-center justify-center gap-3">
            {phase === 'loading' ? (
              <>
                <Loader2 className="h-8 w-8 animate-spin text-white/50" aria-hidden />
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
                  Securing session
                </p>
              </>
            ) : phase === 'missing-token' ? (
              <p className="text-center text-xs text-amber-200/90">No token found in this URL.</p>
            ) : phase === 'needs-signin' ? (
              <p className="text-center text-xs leading-relaxed text-text-secondary">
                Open <span className="text-white/80">home</span>, sign in, then this page will continue automatically if
                you keep this tab open.
              </p>
            ) : phase === 'completing' ? (
              sessionReady && tenantId ? (
                <div className="flex items-center gap-2 text-sm text-emerald-200/95">
                  <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden />
                  Redirecting to dashboard…
                </div>
              ) : (
                <>
                  <Loader2 className="h-8 w-8 animate-spin text-white/50" aria-hidden />
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
                    Applying invite
                  </p>
                </>
              )
            ) : null}
          </div>

          <div className="mt-8 border-t border-white/[0.06] pt-8">
            <Link
              href="/"
              className="flex w-full items-center justify-center rounded-xl border border-white/12 bg-white/[0.04] py-3 text-sm font-medium text-white transition-colors duration-200 hover:border-white/20 hover:bg-white/[0.07]"
            >
              Back to home
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function AcceptClientPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-bg-base">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-white/40" aria-hidden />
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">Loading</span>
          </div>
        </div>
      }
    >
      <AcceptClientInner />
    </Suspense>
  );
}
