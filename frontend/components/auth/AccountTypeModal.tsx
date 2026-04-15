'use client';

import { useState } from 'react';
import { ArrowLeft, Building2, Eye, EyeOff, KeyRound, Loader2, LogIn, UserRound } from 'lucide-react';

type Props = {
  open: boolean;
  busy: boolean;
  infoMessage: string | null;
  onChoose: (t: 'SYSTEM_OWNER' | 'CLIENT_USER') => void;
  /** When true, hide type selection and show credential-entry form. */
  clientEntryMode?: boolean;
  /** Called with email + password when the user submits client credentials. */
  onClientSignIn?: (email: string, password: string) => Promise<void>;
  /** Go back from credential-entry to type selection. */
  onClientBack?: () => void;
};

export function AccountTypeModal({
  open,
  busy,
  infoMessage,
  onChoose,
  clientEntryMode = false,
  onClientSignIn,
  onClientBack,
}: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  if (!open) return null;

  async function handleClientSignIn(e: React.FormEvent) {
    e.preventDefault();
    if (!onClientSignIn) return;
    setLocalError(null);
    if (!email.trim()) { setLocalError('Email is required.'); return; }
    if (!password) { setLocalError('Password is required.'); return; }
    try {
      await onClientSignIn(email.trim(), password);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Sign-in failed. Check your credentials.';
      setLocalError(msg);
    }
  }

  /* ── CLIENT CREDENTIAL ENTRY ──────────────────────────────────── */
  if (clientEntryMode) {
    return (
      <div
        className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md sm:p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="client-entry-title"
      >
        <div className="bastionfed-onboard-surface w-full max-w-lg rounded-2xl border border-white/[0.08] bg-bg-surface p-6 shadow-[0_24px_80px_-20px_rgba(0,0,0,0.85)] ring-1 ring-white/[0.05] sm:p-8">
          {/* Back */}
          {onClientBack && !busy ? (
            <button
              type="button"
              onClick={() => { setLocalError(null); onClientBack(); }}
              className="mb-5 flex items-center gap-1.5 text-xs text-text-muted transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/30"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              Back
            </button>
          ) : null}

          <div className="mb-6 space-y-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">Client access</p>
            <h2 id="client-entry-title" className="font-display text-xl font-bold tracking-tight text-white sm:text-2xl">
              Sign in with your credentials
            </h2>
            <p className="text-sm leading-relaxed text-text-secondary">
              Client accounts are provisioned by your BastionFed administrator — you cannot
              self-register. If you have received your credentials by email, enter them below.
              Otherwise, contact your admin.
            </p>
          </div>

          {/* Info / error message */}
          {(infoMessage || localError) ? (
            <div
              role="alert"
              className="mb-5 rounded-xl border border-amber-500/30 bg-amber-500/[0.08] px-4 py-3 text-sm leading-relaxed text-amber-100/95"
            >
              {infoMessage ?? localError}
            </div>
          ) : null}

          <form onSubmit={(e) => void handleClientSignIn(e)} className="space-y-3" noValidate>
            {/* Email */}
            <div>
              <label htmlFor="client-email" className="mb-1.5 block text-xs font-medium text-text-secondary">
                Email address
              </label>
              <input
                id="client-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setLocalError(null); }}
                disabled={busy}
                placeholder="you@example.com"
                className="w-full rounded-xl border border-border-default bg-bg-base px-4 py-2.5 text-sm text-white placeholder:text-text-muted focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/20 disabled:opacity-50"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="client-password" className="mb-1.5 block text-xs font-medium text-text-secondary">
                Password
              </label>
              <div className="relative">
                <input
                  id="client-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setLocalError(null); }}
                  disabled={busy}
                  placeholder="Your admin-provided password"
                  className="w-full rounded-xl border border-border-default bg-bg-base px-4 py-2.5 pr-10 text-sm text-white placeholder:text-text-muted focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/20 disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted transition-colors hover:text-white focus-visible:outline-none"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="mt-1 flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:border-white/25 hover:bg-white/[0.1] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/40 disabled:pointer-events-none disabled:opacity-45"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <LogIn className="h-4 w-4" aria-hidden />
              )}
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="mt-5 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
            <div className="flex items-start gap-2.5">
              <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" aria-hidden />
              <p className="text-[11px] leading-relaxed text-text-muted">
                Your credentials were sent to you by your BastionFed administrator. Once signed in,
                you will only see data scoped to your assigned site.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ── TYPE SELECTION (first-time setup) ──────────────────────────── */
  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="account-type-title"
      aria-describedby="account-type-desc"
    >
      <div className="bastionfed-onboard-surface w-full max-w-lg rounded-2xl border border-white/[0.08] bg-bg-surface p-6 shadow-[0_24px_80px_-20px_rgba(0,0,0,0.85)] ring-1 ring-white/[0.05] sm:p-8">
        <div className="mb-6 space-y-2 text-center sm:text-left">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">One-time setup</p>
          <h2 id="account-type-title" className="font-display text-xl font-bold tracking-tight text-white sm:text-2xl">
            How will you use BastionFed?
          </h2>
          <p id="account-type-desc" className="text-sm leading-relaxed text-text-secondary">
            Pick the path that matches your role. Admins and owners use their Google workspace
            account. Client users must sign in with admin-issued credentials.
          </p>
        </div>

        {infoMessage ? (
          <div
            role="status"
            className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/[0.08] px-4 py-3 text-sm leading-relaxed text-amber-100/95"
          >
            {infoMessage}
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
          <button
            type="button"
            disabled={busy}
            onClick={() => onChoose('SYSTEM_OWNER')}
            className="group flex flex-col items-start gap-3 rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.06] to-transparent p-4 text-left transition-all duration-200 hover:border-white/20 hover:from-white/[0.09] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/35 disabled:pointer-events-none disabled:opacity-45 sm:p-5"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.06] text-white transition-colors group-hover:border-white/20 group-hover:bg-white/[0.1]">
              <Building2 className="h-5 w-5" aria-hidden />
            </span>
            <span>
              <span className="block font-medium text-white">System owner / Admin</span>
              <span className="mt-1 block text-xs leading-relaxed text-text-secondary">
                Create or run the full tenant — topology, FL clients, operations.
              </span>
            </span>
          </button>

          <button
            type="button"
            disabled={busy}
            onClick={() => onChoose('CLIENT_USER')}
            className="group flex flex-col items-start gap-3 rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.06] to-transparent p-4 text-left transition-all duration-200 hover:border-white/20 hover:from-white/[0.09] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/35 disabled:pointer-events-none disabled:opacity-45 sm:p-5"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.06] text-white transition-colors group-hover:border-white/20 group-hover:bg-white/[0.1]">
              <UserRound className="h-5 w-5" aria-hidden />
            </span>
            <span>
              <span className="block font-medium text-white">Client / Site user</span>
              <span className="mt-1 block text-xs leading-relaxed text-text-secondary">
                Hospital or FL node operator — sign in with credentials from your admin.
              </span>
            </span>
          </button>
        </div>

        {busy ? (
          <div className="mt-6 flex items-center justify-center gap-2 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin text-white/70" aria-hidden />
            <span>Setting up your workspace…</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
