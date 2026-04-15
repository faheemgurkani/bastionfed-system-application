'use client';

import { useId, useState } from 'react';
import {
  Building2,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Mail,
  Monitor,
  PlusCircle,
  SkipForward,
  Trash2,
  UserRound,
  XCircle,
} from 'lucide-react';

// ---- types ----
export type ClientType = 'PERSON' | 'DEVICE';

export interface ClientDef {
  id: string;
  nodeName: string;
  clientType: ClientType;
  email: string;
}

export interface ClientProvisionResult {
  nodeName: string;
  clientType: string;
  status: string; // "created" | "error" | "email_failed"
  clientId?: string | null;
  email?: string | null;
  error?: string | null;
  emailError?: string | null;
  /** Backend identity-only mode: DB registry row only, no Firebase user or credential email. */
  identityOnly?: boolean;
}

interface Props {
  open: boolean;
  busy: boolean;
  onSubmit: (clients: ClientDef[]) => Promise<void>;
  onSkip: () => void;
  results?: ClientProvisionResult[] | null;
  /** Max rows allowed in this submission (per-admin cap remaining). Omit to skip client-side check. */
  remainingSlots?: number | null;
  /** Shown next to limit messaging (e.g. 5). */
  maxClientsPerAdmin?: number | null;
  title?: string;
  description?: string;
  /** If true, hide “Skip for now” (e.g. when adding clients from Settings). */
  hideSkip?: boolean;
}

function uid() {
  return Math.random().toString(36).slice(2);
}

function emptyClient(): ClientDef {
  return { id: uid(), nodeName: '', clientType: 'DEVICE', email: '' };
}

export function AdminSetupWizard({
  open,
  busy,
  onSubmit,
  onSkip,
  results,
  remainingSlots,
  maxClientsPerAdmin,
  title,
  description,
  hideSkip,
}: Props) {
  const baseId = useId();
  const [clients, setClients] = useState<ClientDef[]>([emptyClient()]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  if (!open) return null;

  const heading = title ?? 'Define your clients';
  const blurb =
    description ??
    'Add the nodes that will participate in your federation. Person clients receive login credentials via email; device clients are managed by the admin.';
  const canAddRow =
    remainingSlots == null ? true : remainingSlots < 1 ? false : clients.length < remainingSlots;

  function addRow() {
    if (!canAddRow) return;
    setClients((prev) => [...prev, emptyClient()]);
  }

  function removeRow(id: string) {
    setClients((prev) => prev.filter((c) => c.id !== id));
  }

  function updateRow(id: string, patch: Partial<Omit<ClientDef, 'id'>>) {
    setClients((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    );
    // Clear per-field error when user edits
    if (patch.nodeName !== undefined) {
      setErrors((e) => { const n = { ...e }; delete n[`${id}_name`]; return n; });
    }
    if (patch.email !== undefined) {
      setErrors((e) => { const n = { ...e }; delete n[`${id}_email`]; return n; });
    }
  }

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (remainingSlots != null && remainingSlots >= 0 && clients.length > remainingSlots) {
      errs._form = `You can add at most ${remainingSlots} client(s) in this batch (per-admin limit${maxClientsPerAdmin != null ? ` of ${maxClientsPerAdmin}` : ''}).`;
    }
    for (const c of clients) {
      if (!c.nodeName.trim()) {
        errs[`${c.id}_name`] = 'Node name is required.';
      }
      if (c.clientType === 'PERSON') {
        if (!c.email.trim()) {
          errs[`${c.id}_email`] = 'Email is required for person clients.';
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c.email.trim())) {
          errs[`${c.id}_email`] = 'Enter a valid email address.';
        }
      }
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitted(false);
    await onSubmit(clients);
    setSubmitted(true);
  }

  const hasResults = !!results && results.length > 0;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${baseId}-title`}
    >
      <div className="bastionfed-onboard-surface flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-bg-surface shadow-[0_24px_80px_-20px_rgba(0,0,0,0.9)] ring-1 ring-white/[0.05]">

        {/* header */}
        <div className="shrink-0 border-b border-white/[0.06] px-6 py-5 sm:px-8">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">Admin setup</p>
          <h2 id={`${baseId}-title`} className="mt-1 font-display text-xl font-bold tracking-tight text-white sm:text-2xl">
            {heading}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-text-secondary">{blurb}</p>
          {remainingSlots != null && maxClientsPerAdmin != null ? (
            <p className="mt-2 text-xs font-mono text-amber-200/80">
              You can add up to {remainingSlots} more client(s) in this session (max {maxClientsPerAdmin} per admin
              account).
            </p>
          ) : null}
          {remainingSlots === 0 ? (
            <p className="mt-2 text-xs text-red-400">
              You have reached the maximum number of clients for this admin account. Contact support if you need
              more capacity.
            </p>
          ) : null}
          {errors._form ? <p className="mt-2 text-xs text-red-400">{errors._form}</p> : null}
        </div>

        {/* results view */}
        {hasResults ? (
          <div className="flex-1 overflow-y-auto px-6 py-5 sm:px-8">
            <div className="space-y-2">
              {results!.map((r, i) => {
                const isOk = r.status === 'created';
                const isEmailFail = r.status === 'email_failed';
                const isErr = r.status === 'error';
                return (
                  <div
                    key={i}
                    className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${
                      isErr
                        ? 'border-red-500/25 bg-red-500/[0.06]'
                        : isEmailFail
                        ? 'border-amber-500/25 bg-amber-500/[0.06]'
                        : 'border-emerald-500/20 bg-emerald-500/[0.05]'
                    }`}
                  >
                    {isErr ? (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden />
                    ) : (
                      <CheckCircle2
                        className={`mt-0.5 h-4 w-4 shrink-0 ${isEmailFail ? 'text-amber-300' : 'text-emerald-400'}`}
                        aria-hidden
                      />
                    )}
                    <div className="min-w-0">
                      <p className="font-medium text-white">{r.nodeName}</p>
                      {isErr && r.error ? (
                        <p className="mt-0.5 text-[11px] text-red-300/90">{r.error}</p>
                      ) : null}
                      {isEmailFail && r.emailError ? (
                        <p className="mt-0.5 text-[11px] text-amber-200/80">
                          Client created, but email delivery failed: {r.emailError}
                        </p>
                      ) : null}
                      {isOk && r.identityOnly ? (
                        <p className="mt-0.5 text-[11px] text-emerald-200/60">
                          Database registry created only — no credential email or client-side sync.
                        </p>
                      ) : null}
                      {isOk && !r.identityOnly && r.email ? (
                        <p className="mt-0.5 text-[11px] text-emerald-200/70">
                          Credentials sent to {r.email}
                        </p>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* form view */
          <div className="flex-1 overflow-y-auto px-6 py-5 sm:px-8">
            <div className="space-y-3">
              {clients.map((c, idx) => (
                <div
                  key={c.id}
                  className="rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.03] to-transparent p-4"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted">
                      Client {idx + 1}
                    </p>
                    {clients.length > 1 ? (
                      <button
                        type="button"
                        onClick={() => removeRow(c.id)}
                        className="rounded p-1 text-text-muted transition-colors hover:text-red-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/30"
                        aria-label={`Remove client ${idx + 1}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </button>
                    ) : null}
                  </div>

                  {/* Type toggle */}
                  <div className="mb-3 flex gap-2">
                    {(['DEVICE', 'PERSON'] as ClientType[]).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => updateRow(c.id, { clientType: t, email: '' })}
                        className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border py-2 text-xs font-medium transition-all duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-white/40 ${
                          c.clientType === t
                            ? 'border-white/25 bg-white/[0.1] text-white'
                            : 'border-white/[0.06] bg-transparent text-text-secondary hover:border-white/15 hover:text-white'
                        }`}
                      >
                        {t === 'DEVICE' ? (
                          <Monitor className="h-3.5 w-3.5" aria-hidden />
                        ) : (
                          <UserRound className="h-3.5 w-3.5" aria-hidden />
                        )}
                        {t === 'DEVICE' ? 'Device' : 'Person'}
                      </button>
                    ))}
                  </div>

                  {/* Node name */}
                  <div className="mb-2.5">
                    <label className="block">
                      <span className="sr-only">Node name</span>
                      <input
                        type="text"
                        placeholder="Node name (e.g. Radiology Wing, ICU Hub)"
                        value={c.nodeName}
                        onChange={(e) => updateRow(c.id, { nodeName: e.target.value })}
                        className={`w-full rounded-lg border py-2 pl-3 pr-3 text-sm text-white placeholder:text-text-muted/70 transition-colors focus:outline-none focus:ring-1 ${
                          errors[`${c.id}_name`]
                            ? 'border-red-500/50 bg-red-500/[0.05] focus:border-red-400/60 focus:ring-red-400/20'
                            : 'border-border-default bg-bg-base focus:border-white/30 focus:ring-white/20'
                        }`}
                      />
                    </label>
                    {errors[`${c.id}_name`] ? (
                      <p className="mt-1 text-[11px] text-red-400">{errors[`${c.id}_name`]}</p>
                    ) : null}
                  </div>

                  {/* Email — only for PERSON */}
                  {c.clientType === 'PERSON' ? (
                    <div>
                      <label className="block">
                        <span className="sr-only">Email address</span>
                        <div className="relative">
                          <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" aria-hidden />
                          <input
                            type="email"
                            placeholder="client@example.com — receives login credentials"
                            value={c.email}
                            onChange={(e) => updateRow(c.id, { email: e.target.value })}
                            className={`w-full rounded-lg border py-2 pl-10 pr-3 text-sm text-white placeholder:text-text-muted/70 transition-colors focus:outline-none focus:ring-1 ${
                              errors[`${c.id}_email`]
                                ? 'border-red-500/50 bg-red-500/[0.05] focus:border-red-400/60 focus:ring-red-400/20'
                                : 'border-border-default bg-bg-base focus:border-white/30 focus:ring-white/20'
                            }`}
                          />
                        </div>
                      </label>
                      {errors[`${c.id}_email`] ? (
                        <p className="mt-1 text-[11px] text-red-400">{errors[`${c.id}_email`]}</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-[11px] text-text-muted">
                      Device node — no user credentials needed.
                    </p>
                  )}
                </div>
              ))}

              <button
                type="button"
                onClick={addRow}
                disabled={!canAddRow}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 px-4 py-2.5 text-sm text-text-muted transition-all duration-150 hover:border-white/25 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/30 disabled:opacity-40 disabled:pointer-events-none"
              >
                <PlusCircle className="h-4 w-4" aria-hidden />
                Add another client
              </button>
            </div>
          </div>
        )}

        {/* footer actions */}
        <div className="shrink-0 border-t border-white/[0.06] px-6 py-4 sm:px-8">
          {hasResults ? (
            <button
              type="button"
              onClick={onSkip}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-white/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
            >
              <ChevronRight className="h-4 w-4" aria-hidden />
              Continue to dashboard
            </button>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
              <button
                type="button"
                disabled={busy || remainingSlots === 0}
                onClick={() => void handleSubmit()}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-white/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Building2 className="h-4 w-4" aria-hidden />}
                {busy ? 'Provisioning clients…' : 'Provision clients & continue'}
              </button>
              {!hideSkip ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={onSkip}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-white/15 px-4 py-2.5 text-sm font-medium text-text-secondary transition-all hover:border-white/25 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/30 disabled:opacity-45"
                >
                  <SkipForward className="h-3.5 w-3.5" aria-hidden />
                  Skip for now
                </button>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
